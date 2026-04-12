#!/bin/bash
# generate-drift-report.sh
# Generates drift report JSON including CloudTrail actor attribution
# Usage: ./generate-drift-report.sh <attributed_file> <output_json>

set -e

ATTRIBUTED_FILE="${1:-/tmp/drift_resources_attributed.txt}"
OUTPUT_JSON="${2:-/tmp/drift_report.json}"

if [ ! -f "$ATTRIBUTED_FILE" ]; then
    echo "Error: Attributed file not found: $ATTRIBUTED_FILE" >&2
    exit 1
fi

echo "Generating drift report JSON with actor attribution..."
echo "Input: $ATTRIBUTED_FILE"
echo "Output: $OUTPUT_JSON"

# Get environment variables with defaults
ENVIRONMENT="${ENVIRONMENT:-dev}"
BRANCH="${GITHUB_REF_NAME:-unknown}"
RUN_ID="${GITHUB_RUN_ID:-unknown}"
RUN_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-unknown}/actions/runs/${GITHUB_RUN_ID:-unknown}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Start building resource_changes array
CHANGES="[]"

# Parse each line from attributed file
# Format: address|action|resource_type|identifier|actor_name|actor_arn|event_time
while IFS='|' read -r address action resource_type identifier actor_name actor_arn event_time; do
    [ -z "$address" ] && continue
    
    # Extract resource name from address (last segment after final dot)
    resource_name=$(echo "$address" | awk -F'.' '{print $NF}' | tr -d '[]"')
    
    # Normalize resource_type if it's "unknown"
    if [ -z "$resource_type" ] || [ "$resource_type" = "unknown" ]; then
        resource_type=$(echo "$address" | grep -oE 'aws_[a-z0-9_]+' | tail -1)
        [ -z "$resource_type" ] && resource_type="unknown"
    fi
    
    # Normalize action to valid ActionType (create, update, delete, replace, no-op)
    case "$action" in
        create|update|delete|replace|no-op) ;;  # valid, keep as-is
        *created*) action="create" ;;
        *updated*) action="update" ;;
        *destroyed*|*deleted*) action="delete" ;;
        *replaced*) action="replace" ;;
        *) action="update" ;;  # default fallback
    esac

    # Build resource change JSON object
    change_obj=$(jq -n \
        --arg rt "$resource_type" \
        --arg rn "$resource_name" \
        --arg act "$action" \
        --arg an "$actor_name" \
        --arg aa "$actor_arn" \
        --arg et "$event_time" \
        '{
            resource_type: $rt,
            resource_name: $rn,
            action: $act,
            actor_name: (if $an == "" or $an == "-" or $an == "*(unavailable)*" then null else $an end),
            actor_arn: (if $aa == "" or $aa == "-" then null else $aa end),
            event_time: (if $et == "" or $et == "-" then null else $et end)
        }')
    
    # Add to changes array
    CHANGES=$(echo "$CHANGES" | jq --argjson obj "$change_obj" '. + [$obj]')
    
done < "$ATTRIBUTED_FILE"

# Determine if drift was detected
DRIFT_DETECTED=true
CHANGE_COUNT=$(echo "$CHANGES" | jq 'length')
if [ "$CHANGE_COUNT" -eq 0 ]; then
    DRIFT_DETECTED=false
fi

# Write final JSON report
jq -n \
    --arg ts "$TIMESTAMP" \
    --arg env "$ENVIRONMENT" \
    --arg branch "$BRANCH" \
    --arg run_id "$RUN_ID" \
    --arg run_url "$RUN_URL" \
    --argjson drift "$DRIFT_DETECTED" \
    --argjson changes "$CHANGES" \
    '{
        timestamp: $ts,
        environment: $env,
        branch: $branch,
        workflow_run_id: $run_id,
        workflow_run_url: $run_url,
        drift_detected: $drift,
        resource_changes: $changes
    }' > "$OUTPUT_JSON"

echo "✅ Drift report JSON generated: $OUTPUT_JSON"
echo "   Environment: $ENVIRONMENT"
echo "   Drift detected: $DRIFT_DETECTED"
echo "   Resources: $CHANGE_COUNT"

# Show sample of generated JSON
echo ""
echo "Sample output:"
jq '.' "$OUTPUT_JSON" | head -30
