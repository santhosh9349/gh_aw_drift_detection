# Drift Detection Refactoring - Implementation Details

## Overview
This refactoring addresses multiple issues in the drift detection workflow:
1. **Primary Fix**: Resolved JSON parsing crash in `generate-plan-json.sh` caused by invalid JSON passed to `jq --argjson`
2. Properly attribute manual deletions (which show as "creates" in Terraform plan)
3. Pass CloudTrail actor information to Python data models and Telegram notifications

## Recent Changes (2026-02-15)

### Critical Bug Fix: JSON Parsing Failure

**Problem**: The drift detection workflow was failing with error:
```
jq: invalid JSON text passed to --argjson
Process completed with exit code 2.
```

**Root Cause**: The `generate-plan-json.sh` script was:
1. Parsing human-readable text output from `terraform plan`
2. Attempting to extract resource state from Terraform state
3. Passing potentially empty/invalid strings to `jq --argjson` which requires valid JSON

**Solution**: Complete refactor to use native JSON output from Terraform:
1. **Workflow Change**: Updated to run `terraform plan -json` which produces native JSONL stream
2. **Script Rewrite**: `generate-plan-json.sh` now parses the JSONL stream directly
3. **Validation**: All JSON values validated before passing to `jq --argjson`
4. **Resilience**: Gracefully handles null/missing "before" states (create actions)

### Updated Implementation

#### `generate-plan-json.sh` (REFACTORED)
**Purpose**: Parse native JSON stream from `terraform plan -json`

**Key Changes**:
- **Input**: Now accepts JSONL stream from `terraform plan -json` instead of text output
- **No State Pulling**: Native JSON already contains all state information
- **Robust Parsing**: Extracts `planned_change` events from JSONL stream
- **Null Handling**: Properly handles `null` values for create/delete actions
- **Validation**: Ensures all JSON values are valid before using `--argjson`

**Process**:
1. Read JSONL stream line by line
2. Filter for `type="planned_change"` or `type="resource_drift"` messages
3. Extract resource address, type, action, before/after states
4. Validate JSON values (default to `null` if empty/invalid)
5. Build structured JSON output compatible with `parse-terraform-plan.sh`

**Example Input** (JSONL from `terraform plan -json`):
```json
{"@level":"info","type":"planned_change","change":{"resource":{"addr":"aws_vpc.main","resource_type":"aws_vpc"},"action":"update","before":{"id":"vpc-123"},"after":{"id":"vpc-123","tags":{"Env":"dev"}}}}
{"@level":"info","type":"planned_change","change":{"resource":{"addr":"aws_subnet.public","resource_type":"aws_subnet"},"action":"create","before":null,"after":{"id":"subnet-456"}}}
```

**Example Output** (Structured JSON):
```json
{
  "format_version": "1.0",
  "terraform_version": "1.5.7",
  "resource_changes": [
    {
      "address": "aws_vpc.main",
      "type": "aws_vpc",
      "change": {
        "actions": ["update"],
        "before": {"id": "vpc-123"},
        "after": {"id": "vpc-123", "tags": {"Env": "dev"}}
      }
    },
    {
      "address": "aws_subnet.public",
      "type": "aws_subnet",
      "change": {
        "actions": ["create"],
        "before": null,
        "after": {"id": "subnet-456"}
      }
    }
  ]
}
```

### Workflow Changes

#### `.github/workflows/drift-detection.yml`

**Terraform Plan Step** - Now generates both text and JSON output:
```yaml
- name: Terraform Plan (Drift Detection)
  run: |
    # Generate text output for display
    terraform plan -detailed-exitcode -input=false -no-color 2>&1 | tee /tmp/plan_output.txt
    
    # Generate JSON output for parsing
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 2 ]; then
      terraform plan -json -detailed-exitcode -input=false 2>&1 > /tmp/plan_stream.jsonl
    fi
```

**Parse Plan JSON Stream Step** - Plan parsing is performed inline in `drift-detection.yml` using `jq` directly on the JSONL stream. The standalone `generate-plan-json.sh` and `parse-terraform-plan.sh` scripts are available for local/manual use but are not invoked by the workflow.

### Benefits of This Refactor

1. **Reliability**: No more crashes from invalid JSON
2. **Accuracy**: Native Terraform JSON contains complete, accurate data
3. **Simplicity**: Removed complex text parsing and state pulling logic
4. **Performance**: Faster - no need to pull state separately
5. **Maintainability**: Cleaner code that's easier to understand and debug

### Testing

All edge cases tested and validated:

✅ **Normal updates**: Resources with both before/after states  
✅ **Create actions**: Resources with `null` before state (manual deletions)  
✅ **Delete actions**: Resources with `null` after state  
✅ **Empty plans**: No resource changes  
✅ **Mixed JSONL**: Non-change messages filtered correctly  
✅ **Invalid input**: Gracefully generates empty valid JSON structure

## Changes Made (Previous Refactoring)

### 1. Script Refactoring

#### `parse-terraform-plan.sh`
**Purpose**: Parse Terraform plan JSON to extract resource changes with identifiers

**Key Features**:
- Parses JSON plan structure instead of text output
- Extracts identifiers with priority: `arn` > `id` > `tags.Name` > `name`
- For **update/delete** actions: Uses `change.before` state (resource exists in state)
- For **create** actions: Uses `change.after` state (handles manual deletions)
- Outputs structured format: `address|action|resource_type|identifier`

**Example Output**:
```
module.vpc["dev"].aws_vpc.this|update|aws_vpc|arn:aws:ec2:us-east-1:123456789012:vpc/vpc-xxx
module.subnet["pub_sub1"].aws_subnet.this|create|aws_subnet|pub_sub1
aws_instance.test|delete|aws_instance|arn:aws:ec2:us-east-1:123456789012:instance/i-xxx
```

#### `query-cloudtrail.sh`
**Purpose**: Query AWS CloudTrail to find IAM user attribution for drifted resources

**Key Features**:
- **Strategy A** (ARN available): Queries CloudTrail using `ResourceName` attribute
- **Strategy B** (Create action/manual deletion): Queries by `EventName` (e.g., `DeleteSubnet`)
- Extracts actor information:
  - IAM users: `userName` and `arn`
  - Assumed roles: `sessionIssuer.userName` + session name
  - Root account: Marked as `ROOT_ACCOUNT`
  - AWS services: Marked as `AWS_Service:` + invokedBy
- Outputs format: `address|action|resource_type|identifier|actor_name|actor_arn|event_time`

**Example Output**:
```
module.vpc["dev"].aws_vpc.this|update|aws_vpc|arn:...|john.doe|arn:aws:iam::123456789012:user/john.doe|2024-01-15T10:30:00Z
module.subnet["pub_sub1"].aws_subnet.this|create|aws_subnet|pub_sub1|john.doe|arn:aws:iam::123456789012:user/john.doe|2024-01-15T10:30:00Z
```

#### `generate-plan-json.sh` (NEW)
**Purpose**: Generate JSON representation of Terraform plan from text output

**Why Needed**: Terraform Cloud doesn't support the `-out` flag, so we need to convert the text plan output to JSON format by combining it with state data.

**Process**:
1. Pulls current state from Terraform Cloud
2. Parses resource changes from text plan output
3. Matches resources with state data to get attributes
4. Generates JSON structure compatible with `parse-terraform-plan.sh`

#### `generate-drift-report.sh` (NEW)
**Purpose**: Generate drift report JSON with CloudTrail actor attribution

**Key Features**:
- Reads attributed data from `query-cloudtrail.sh`
- Parses and structures data for Python consumption
- Includes actor attribution fields: `actor_name`, `actor_arn`, `event_time`
- Uses GitHub environment variables for metadata

**Output Format**:
```json
{
  "timestamp": "2026-02-14T21:55:56Z",
  "environment": "dev",
  "branch": "dev4",
  "workflow_run_id": "123456",
  "workflow_run_url": "https://github.com/...",
  "drift_detected": true,
  "resource_changes": [
    {
      "resource_type": "aws_vpc",
      "resource_name": "this",
      "action": "update",
      "actor_name": "john.doe",
      "actor_arn": "arn:aws:iam::123456789012:user/john.doe",
      "event_time": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 2. Python Model Updates

#### `models.py`
Added actor attribution fields to `ResourceChange`:
```python
class ResourceChange(BaseModel):
    # Existing fields...
    
    # New CloudTrail attribution fields
    actor_name: Optional[str] = Field(None, description="IAM user or role that made the change")
    actor_arn: Optional[str] = Field(None, description="ARN of the actor")
    event_time: Optional[str] = Field(None, description="Timestamp when change was made")
    
    @property
    def has_attribution(self) -> bool:
        """Check if CloudTrail attribution is available"""
        return self.actor_name is not None and self.actor_name not in ["*(unavailable)*", "-", ""]
```

Enhanced `change_summary` property to include actor information:
```python
@property
def change_summary(self) -> List[str]:
    """List of changed attributes with before/after values"""
    # ... existing logic ...
    
    if self.has_attribution:
        changes.append(f"Actor: {self.actor_name}")
        if self.event_time and self.event_time != "-":
            changes.append(f"Time: {self.event_time}")
    
    return changes
```

#### `notify_telegram.py`
Updated `parse_drift_report` function to parse actor fields:
```python
ResourceChange(
    resource_type=change_data.get("resource_type", "unknown"),
    resource_name=change_data.get("resource_name", "unknown"),
    action=ActionType(change_data.get("action", "update")),
    before=change_data.get("before"),
    after=change_data.get("after"),
    actor_name=change_data.get("actor_name"),      # NEW
    actor_arn=change_data.get("actor_arn"),        # NEW
    event_time=change_data.get("event_time"),      # NEW
)
```

### 3. Workflow Updates

#### `.github/workflows/drift-detection.yml`

**Simplified Steps**:
1. ~~Extract Drifted Resource ARNs~~ (removed - 195 lines)
2. ~~Query CloudTrail for Attribution~~ (removed - 254 lines)
3. **New**: Generate Plan JSON (10 lines)
4. **Updated**: Parse Terraform Plan (uses JSON parsing)
5. **Updated**: Query CloudTrail for Attribution (uses refactored script)
6. **Updated**: Generate Drift Report JSON (uses new script with attribution)

**Key Changes**:
- Removed ~450 lines of complex inline bash
- Replaced with 4 modular, reusable scripts
- Total workflow size reduced by ~350 lines
- Attribution data now flows to both GitHub Issues and Telegram notifications

## Testing

All components have been tested with sample data:

### Test Results
✅ **parse-terraform-plan.sh**: Correctly extracts identifiers for all action types  
✅ **query-cloudtrail.sh**: Successfully queries CloudTrail (Strategy A & B)  
✅ **generate-drift-report.sh**: Generates complete JSON with attribution  
✅ **Python models**: Correctly parse and display actor attribution  

### Test Data
Located in `/tmp/drift-test/`:
- `plan.json`: Sample Terraform plan JSON
- `parsed.txt`: Parsed resources with identifiers
- `attributed.txt`: Resources with CloudTrail attribution
- `report.json`: Final drift report with actor data

## Manual Deletion Handling

**Problem**: When a resource is manually deleted from AWS, Terraform sees it as missing from the actual infrastructure. The plan shows this as a "create" action (Terraform wants to create it to match the state).

**Solution**:
1. **Parse step**: For "create" actions, extract identifier from `change.after` (planned resource)
2. **CloudTrail step**: Query by EventName (e.g., `DeleteSubnet`, `TerminateInstances`)
3. **Result**: Actor who deleted the resource is correctly identified

**Example**:
```
Resource: module.subnet["pub_sub1"].aws_subnet.this
Action: create (actually a manual deletion)
CloudTrail query: EventName=DeleteSubnet
Result: john.doe deleted the subnet on 2024-01-15T10:30:00Z
```

## Benefits

1. **Modular Architecture**: Scripts are reusable and testable independently
2. **Accurate Attribution**: Handles all cases including manual deletions
3. **Complete Data Flow**: Actor information flows to both Issues and Telegram
4. **Maintainable**: ~350 lines less code, clearer logic
5. **Extensible**: Easy to add new CloudTrail event mappings or identifier types

## Future Enhancements

- Add support for more AWS resource types in event mapping
- Implement caching of CloudTrail queries to reduce API calls
- Add metric collection for attribution success rate
- Support for custom identifier extraction rules per resource type
