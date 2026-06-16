# JIT Proxy Load Testing Scripts

This directory contains scripts for testing and validating the JIT proxy server functionality.

## Scripts

### test_s3_access.py

Validates that JIT credentials are working correctly by attempting to list an S3 bucket.

**Features:**
- Checks `AWS_CONFIG_FILE` environment variable and validates the file
- Uses boto3 profiles configured by the JIT client
- Verifies credentials with AWS STS
- Lists S3 bucket contents to confirm access

**Requirements:**
```bash
pip install boto3
```

**Usage:**
```bash
# Basic usage
python test_s3_access.py --profile my-project --bucket my-bucket-name

# Show more objects
python test_s3_access.py --profile my-project --bucket my-bucket --max-keys 50

# Use environment variable for profile
export AWS_PROFILE=my-project
python test_s3_access.py --bucket my-bucket
```

**Expected Output:**
```
================================================================================
JIT Credentials S3 Access Test
================================================================================

✓ AWS_CONFIG_FILE is set to: /etc/.aws/profile
✓ AWS config file exists: /etc/.aws/profile
✓ AWS config file has content: 1234 bytes

================================================================================
Testing S3 Access
Profile: my-project
Bucket: my-bucket-name
================================================================================

Creating boto3 session with profile 'my-project'...
✓ Session created successfully

Verifying AWS credentials...
✓ Credentials verified:
  Account: 123456789012
  User ARN: arn:aws:sts::123456789012:assumed-role/jit-role/session-id
  User ID: AROAXXXXXXXXXXXXXXXXX:session-id

Listing contents of bucket 'my-bucket-name'...
✓ Successfully listed bucket contents
```

### stress_test_jit.py

Creates multiple Domino jobs concurrently to stress test the JIT proxy server.

**Features:**
- Creates all jobs simultaneously for maximum stress
- Tracks job creation success/failure
- Monitors job execution status
- Reports throughput and success rates
- Exports detailed results to JSON

**Requirements:**
```bash
pip install dominodatalab
```

**Usage:**
```bash
# Basic stress test with 50 concurrent jobs
export DOMINO_API_HOST=https://domino.company.com
export DOMINO_USER_API_KEY=your-api-key
python stress_test_jit.py --jobs 50 --project myuser/myproject

# High-stress test with custom command
python stress_test_jit.py --jobs 200 --project myuser/myproject \
    --command "aws s3 ls && aws sts get-caller-identity"

# Quick test without waiting for completion
python stress_test_jit.py --jobs 100 --project myuser/myproject --no-wait

# Save detailed results
python stress_test_jit.py --jobs 75 --project myuser/myproject \
    --output results.json
```

## Testing Workflow

1. **Deploy JIT Infrastructure**
   - Ensure JIT proxy server is running
   - Verify domsed webhook is injecting sidecars

2. **Run Stress Test**
   ```bash
   python stress_test_jit.py --jobs 100 --project myuser/myproject
   ```

3. **Validate Credentials in Running Jobs**
   - Exec into a running workspace/job
   - Check that JIT client has created credentials
   ```bash
   ls -la /etc/.aws/
   cat /etc/.aws/profile
   ```

4. **Test S3 Access**
   ```bash
   # Inside a Domino workspace with JIT credentials
   export AWS_CONFIG_FILE=/etc/.aws/profile
   python test_s3_access.py --profile my-project --bucket test-bucket
   ```

## Troubleshooting

### test_s3_access.py

**Problem:** `AWS_CONFIG_FILE environment variable is not set`
- **Solution:** Set the environment variable: `export AWS_CONFIG_FILE=/etc/.aws/profile`

**Problem:** `AWS profile 'my-project' not found`
- **Solution:** Check that the JIT client has created the profile. Run `cat $AWS_CONFIG_FILE` to see available profiles

**Problem:** `Credentials have expired`
- **Solution:** The JIT client sidecar should automatically refresh. Check JIT client logs: `kubectl logs <pod> -c jit-client`

**Problem:** `Access denied to bucket`
- **Solution:** Verify the IAM role associated with your JIT session has the necessary S3 permissions

### stress_test_jit.py

**Problem:** `No jobs were created`
- **Solution:** Check DOMINO_USER_API_KEY is valid and has permissions to create jobs in the project

**Problem:** Jobs created but all failed
- **Solution:** Check job logs in Domino UI. Verify the command is valid and the environment has AWS CLI/boto3 installed

**Problem:** Low success rate
- **Solution:** May indicate JIT proxy server is overloaded. Check server logs and resource utilization

## Monitoring JIT Proxy Server

During stress tests, monitor:

```bash
# Server logs
kubectl logs -n domino-field deployment/jit-svc -f

# Resource usage
kubectl top pod -n domino-field -l app=jit-svc

# Prometheus metrics (if enabled)
curl http://jit-svc.domino-field:8080/metrics
```

## Expected Results

### Successful Test Indicators

1. **Creation Throughput:** 5-20 jobs/second (depends on cluster)
2. **Success Rate:** > 95% for job creation
3. **Credential Retrieval:** < 2 seconds per request
4. **S3 Access:** Successful listing with valid credentials

### Warning Signs

- Creation success rate < 90%
- Credential requests timing out
- JIT proxy server OOM/CPU throttling
- Jobs failing with credential errors
