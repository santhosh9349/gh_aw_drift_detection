#!/bin/bash
# query-cloudtrail.sh
# Queries AWS CloudTrail to find IAM user attribution for drifted resources
# Usage: ./query-cloudtrail.sh [input_file] [output_file]
#
# Input format: address|action|resource_type|identifier (from parse-terraform-plan.sh)
# Output format: address|action|resource_type|identifier|actor_name|actor_arn|event_time

set -e

INPUT_FILE="${1:-/tmp/drift_resources.txt}"
OUTPUT_FILE="${2:-/tmp/drift_resources_attributed.txt}"

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file not found: $INPUT_FILE" >&2
    exit 1
fi

# Start date: 7 days ago (chosen lookback window - CloudTrail retains up to 90 days)
START_TIME=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)

echo "Querying CloudTrail for change attribution..."
echo "Start time: $START_TIME"
echo "Input: $INPUT_FILE"
echo "Output: $OUTPUT_FILE"

# Helper function to check if string is an AWS ARN
is_arn() {
    local str="$1"
    [[ "$str" =~ ^arn:(aws|aws-cn|aws-us-gov):[a-z0-9-]+:[a-z0-9-]*:(([0-9]{12})|aws|):.+ ]]
}

# Helper function to extract actor information from CloudTrail event
extract_actor() {
    local event="$1"
    local user_type=$(echo "$event" | jq -r '.userIdentity.type // "Unknown"')
    
    case "$user_type" in
        IAMUser)
            actor_name=$(echo "$event" | jq -r '.userIdentity.userName // "unknown"')
            actor_arn=$(echo "$event" | jq -r '.userIdentity.arn // "unknown"')
            ;;
        AssumedRole)
            actor_name=$(echo "$event" | jq -r '
                (.userIdentity.sessionContext.sessionIssuer.userName // "unknown") + 
                "/" + 
                (.userIdentity.arn | split("/") | last // "unknown")
            ')
            actor_arn=$(echo "$event" | jq -r '.userIdentity.arn // "unknown"')
            ;;
        Root)
            actor_name="ROOT_ACCOUNT"
            actor_arn=$(echo "$event" | jq -r '.userIdentity.arn // "unknown"')
            ;;
        AWSService)
            actor_name=$(echo "$event" | jq -r '"AWS_Service:" + (.userIdentity.invokedBy // "unknown")')
            actor_arn=$(echo "$event" | jq -r '.userIdentity.invokedBy // "unknown"')
            ;;
        *)
            actor_name=$(echo "$event" | jq -r '.userIdentity.userName // (.userIdentity.arn | split("/") | last) // "unknown"')
            actor_arn=$(echo "$event" | jq -r '.userIdentity.arn // .userIdentity.principalId // "unknown"')
            ;;
    esac
    
    event_time=$(echo "$event" | jq -r '.eventTime // "-"')
}

# Map Terraform resource type to CloudTrail event name for deletions
# This is used when a resource shows as "create" in plan but was deleted from AWS
get_delete_event_name() {
    local tf_type="$1"
    case "$tf_type" in
        aws_vpc) echo "DeleteVpc" ;;
        aws_subnet) echo "DeleteSubnet" ;;
        aws_instance) echo "TerminateInstances" ;;
        aws_security_group) echo "DeleteSecurityGroup" ;;
        aws_iam_role) echo "DeleteRole" ;;
        aws_iam_instance_profile) echo "DeleteInstanceProfile" ;;
        aws_iam_role_policy_attachment) echo "DetachRolePolicy" ;;
        aws_route_table) echo "DeleteRouteTable" ;;
        aws_internet_gateway) echo "DeleteInternetGateway" ;;
        aws_ec2_transit_gateway) echo "DeleteTransitGateway" ;;
        aws_ec2_transit_gateway_vpc_attachment) echo "DeleteTransitGatewayVpcAttachment" ;;
        aws_route_table_association) echo "DisassociateRouteTable" ;;
        *) echo "" ;;
    esac
}

# Clear output file
> "$OUTPUT_FILE"

# Process each drifted resource
while IFS='|' read -r address action resource_type identifier; do
    echo ""
    echo "Processing: $address (action: $action, identifier: $identifier)"
    
    actor_name="*(unavailable)*"
    actor_arn="-"
    event_time="-"
    
    # Strategy A: If identifier is an ARN, query CloudTrail by ResourceName
    if is_arn "$identifier"; then
        echo "  Strategy A: Querying CloudTrail by ARN: $identifier"
        
        CLOUDTRAIL_EVENT=$(aws cloudtrail lookup-events \
            --lookup-attributes AttributeKey=ResourceName,AttributeValue="$identifier" \
            --start-time "$START_TIME" \
            --max-results 1 \
            --query 'Events[0].CloudTrailEvent' \
            --output text 2>/dev/null || echo "")
        
        if [ -n "$CLOUDTRAIL_EVENT" ] && [ "$CLOUDTRAIL_EVENT" != "None" ] && [ "$CLOUDTRAIL_EVENT" != "null" ]; then
            extract_actor "$CLOUDTRAIL_EVENT"
            echo "  ✅ Found via ARN: $actor_name at $event_time"
        else
            echo "  ❌ No CloudTrail events found for ARN"
        fi
        
    # Strategy B: If action is "create" (resource was manually deleted from AWS)
    elif [ "$action" = "create" ]; then
        # Strategy B1: Use old resource ID from resource_drift state to query CloudTrail by ResourceName.
        # This is more precise than querying by EventName alone (which returns any event of that type).
        if [ -n "$identifier" ] && [ "$identifier" != "unknown" ]; then
            echo "  Strategy B1: Querying CloudTrail by old resource ID: $identifier (manual deletion detected)"
            
            CLOUDTRAIL_EVENT=$(aws cloudtrail lookup-events \
                --lookup-attributes AttributeKey=ResourceName,AttributeValue="$identifier" \
                --start-time "$START_TIME" \
                --max-results 1 \
                --query 'Events[0].CloudTrailEvent' \
                --output text 2>/dev/null || echo "")
            
            if [ -n "$CLOUDTRAIL_EVENT" ] && [ "$CLOUDTRAIL_EVENT" != "None" ] && [ "$CLOUDTRAIL_EVENT" != "null" ]; then
                extract_actor "$CLOUDTRAIL_EVENT"
                echo "  ✅ Found via old resource ID: $actor_name at $event_time"
            else
                echo "  ❌ No CloudTrail events found for resource ID: $identifier"
            fi
        fi

        # Strategy B2: Fallback — query by delete EventName if no result from B1
        if [ "$actor_name" = "*(unavailable)*" ]; then
            delete_event=$(get_delete_event_name "$resource_type")

            if [ -n "$delete_event" ]; then
                echo "  Strategy B2: Querying CloudTrail by EventName: $delete_event (fallback)"
                
                CLOUDTRAIL_EVENT=$(aws cloudtrail lookup-events \
                    --lookup-attributes AttributeKey=EventName,AttributeValue="$delete_event" \
                    --start-time "$START_TIME" \
                    --max-results 1 \
                    --query 'Events[0].CloudTrailEvent' \
                    --output text 2>/dev/null || echo "")
                
                if [ -n "$CLOUDTRAIL_EVENT" ] && [ "$CLOUDTRAIL_EVENT" != "None" ] && [ "$CLOUDTRAIL_EVENT" != "null" ]; then
                    extract_actor "$CLOUDTRAIL_EVENT"
                    echo "  ✅ Found via EventName: $actor_name at $event_time"
                else
                    echo "  ❌ No CloudTrail events found for event: $delete_event"
                fi
            else
                echo "  ⚠️  No CloudTrail event mapping for resource type: $resource_type"
            fi
        fi
    else
        echo "  ⚠️  Identifier is not an ARN and action is not 'create' - cannot query CloudTrail"
    fi
    
    # Write to output file
    echo "${address}|${action}|${resource_type}|${identifier}|${actor_name}|${actor_arn}|${event_time}" >> "$OUTPUT_FILE"
    
    # Rate limiting: sleep 0.5s between queries
    sleep 0.5
    
done < "$INPUT_FILE"

echo ""
echo "CloudTrail attribution complete"
echo "Results written to: $OUTPUT_FILE"
echo ""
echo "Summary:"
cat "$OUTPUT_FILE"
