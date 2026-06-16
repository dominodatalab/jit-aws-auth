#!/usr/bin/env python
"""
Stress Test Script for JIT Proxy Server

This script creates multiple Domino jobs concurrently to stress test the jit-proxy-server
by triggering simultaneous credential requests.

Requirements:
    pip install dominodatalab

Usage:
    python stress_test_jit.py --jobs 50 --project myuser/myproject --command "aws s3 ls"

Environment Variables:
    DOMINO_API_HOST - Domino API endpoint (e.g., https://domino.company.com)
    DOMINO_USER_API_KEY - Domino API key for authentication
"""

import argparse
import os
import sys
import time
import json
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from domino import Domino
except ImportError:
    print("Error: dominodatalab package not found. Install with: pip install dominodatalab")
    sys.exit(1)


class JitStressTest:
    """Manages stress testing of the JIT proxy server via Domino jobs"""

    def __init__(
        self,
        api_host: str,
        api_key: str,
        project: str,
        num_jobs: int,
        command: str,
        hardware_tier_name: Optional[str] = None,
        environment_id: Optional[str] = None,
        wait_for_completion: bool = True,
        timeout: int = 600,
        poll_interval: int = 5
    ):
        """
        Initialize the stress test

        Args:
            api_host: Domino API host URL
            api_key: Domino API key
            project: Domino project (owner/project-name format)
            num_jobs: Number of jobs to create concurrently
            command: Command to run in each job (should trigger AWS access)
            hardware_tier_name: Hardware tier name (optional)
            environment_id: Environment ID (optional)
            wait_for_completion: Whether to wait for all jobs to complete
            timeout: Timeout in seconds for waiting for job completion
            poll_interval: Seconds between status polls
        """
        self.api_host = api_host
        self.api_key = api_key
        self.project = project
        self.num_jobs = num_jobs
        self.command = command
        self.hardware_tier_name = hardware_tier_name
        self.environment_id = environment_id
        self.wait_for_completion = wait_for_completion
        self.timeout = timeout
        self.poll_interval = poll_interval

        # Initialize Domino client
        print(f"Connecting to Domino at {api_host}...")
        self.domino = Domino(
            project=project,
            api_key=api_key,
            host=api_host
        )

        # Track results
        self.job_ids: List[str] = []
        self.results: Dict[str, Dict] = {}
        self.start_time = None
        self.end_time = None
        self.creation_errors: List[Dict] = []

    def create_single_job(self, job_number: int) -> Tuple[int, Optional[str], bool, str]:
        """
        Create a single Domino job

        Args:
            job_number: Sequential job number for tracking

        Returns:
            Tuple of (job_number, job_id, success, error_message)
        """
        try:
            job_params = {
                'command': self.command,
                'title': f'JIT Stress Test Job #{job_number}',
                'hardware_tier_name': self.hardware_tier_name,
                'environment_id': self.environment_id,
                'commit_id': None  # Use latest commit
            }

            # Remove None values
            job_params = {k: v for k, v in job_params.items() if v is not None}

            # Start the job
            response = self.domino.job_start(**job_params)

            # The response should contain 'id' field
            if isinstance(response, dict) and 'id' in response:
                job_id = response['id']
                print(f"✓ Created job #{job_number}: {job_id}")
                return (job_number, job_id, True, "")
            else:
                error_msg = f"Unexpected response format: {response}"
                print(f"✗ Failed to create job #{job_number}: {error_msg}")
                return (job_number, None, False, error_msg)

        except Exception as e:
            error_msg = str(e)
            print(f"✗ Exception creating job #{job_number}: {error_msg}")
            return (job_number, None, False, error_msg)

    def create_jobs_concurrent(self) -> List[str]:
        """
        Create all jobs concurrently to maximize stress on the JIT proxy server

        Returns:
            List of successfully created job IDs
        """
        print(f"\n{'='*80}")
        print(f"Creating {self.num_jobs} jobs CONCURRENTLY")
        print(f"Project: {self.project}")
        print(f"Command: {self.command}")
        if self.hardware_tier_name:
            print(f"Hardware Tier: {self.hardware_tier_name}")
        if self.environment_id:
            print(f"Environment ID: {self.environment_id}")
        print(f"{'='*80}\n")

        successful_jobs = []
        creation_start = time.time()

        # Use ThreadPoolExecutor with max_workers = num_jobs for full concurrency
        with ThreadPoolExecutor(max_workers=self.num_jobs) as executor:
            # Submit all job creation tasks at once
            future_to_job = {
                executor.submit(self.create_single_job, i): i
                for i in range(1, self.num_jobs + 1)
            }

            # Collect results as they complete
            for future in as_completed(future_to_job):
                job_number, job_id, success, error = future.result()

                if success and job_id:
                    successful_jobs.append(job_id)
                    self.results[job_id] = {
                        'job_number': job_number,
                        'created': True,
                        'created_at': datetime.now().isoformat(),
                        'status': 'Running',
                        'error': None
                    }
                else:
                    self.creation_errors.append({
                        'job_number': job_number,
                        'error': error
                    })

        creation_duration = time.time() - creation_start

        print(f"\n{'='*80}")
        print(f"Job Creation Summary:")
        print(f"  ✓ Successful: {len(successful_jobs)}/{self.num_jobs}")
        print(f"  ✗ Failed: {len(self.creation_errors)}/{self.num_jobs}")
        print(f"  Duration: {creation_duration:.2f}s")
        if creation_duration > 0:
            print(f"  Throughput: {len(successful_jobs)/creation_duration:.2f} jobs/second")
        print(f"{'='*80}\n")

        if self.creation_errors:
            print("Failed job creations:")
            for fail in self.creation_errors[:10]:  # Show first 10
                print(f"  Job #{fail['job_number']}: {fail['error']}")
            if len(self.creation_errors) > 10:
                print(f"  ... and {len(self.creation_errors) - 10} more")
            print()

        return successful_jobs

    def get_job_status(self, job_id: str) -> Dict:
        """
        Get the current status of a job

        Args:
            job_id: The job ID to check

        Returns:
            Dictionary with job status information
        """
        try:
            status = self.domino.job_status(job_id)
            return status
        except Exception as e:
            return {
                'statuses': {'executionStatus': 'Error'},
                'error': str(e)
            }

    def wait_for_jobs(self):
        """Wait for all jobs to complete and collect results"""
        if not self.job_ids:
            print("No jobs to wait for")
            return

        print(f"\n{'='*80}")
        print(f"Waiting for {len(self.job_ids)} jobs to complete")
        print(f"Timeout: {self.timeout}s | Poll Interval: {self.poll_interval}s")
        print(f"{'='*80}\n")

        start_wait = time.time()
        completed = set()
        last_progress_update = 0

        while len(completed) < len(self.job_ids):
            elapsed = time.time() - start_wait

            if elapsed > self.timeout:
                print(f"\n⚠ Timeout reached after {self.timeout}s")
                print(f"   Completed: {len(completed)}/{len(self.job_ids)}")
                break

            for job_id in self.job_ids:
                if job_id in completed:
                    continue

                status = self.get_job_status(job_id)
                exec_status = status.get('statuses', {}).get('executionStatus', 'Unknown')

                # Terminal states
                if exec_status in ['Succeeded', 'Failed', 'Error', 'Stopped']:
                    completed.add(job_id)
                    job_num = self.results[job_id]['job_number']
                    self.results[job_id]['status'] = exec_status
                    self.results[job_id]['completed_at'] = datetime.now().isoformat()

                    if exec_status == 'Succeeded':
                        print(f"✓ Job #{job_num:3d} ({job_id}): {exec_status}")
                    else:
                        print(f"✗ Job #{job_num:3d} ({job_id}): {exec_status}")
                        if 'error' in status:
                            self.results[job_id]['error'] = status['error']

            # Progress update every 10 seconds
            if elapsed - last_progress_update >= 10:
                print(f"\n[{elapsed:.0f}s] Progress: {len(completed)}/{len(self.job_ids)} completed")
                last_progress_update = elapsed

            time.sleep(self.poll_interval)

        self.end_time = datetime.now()
        print(f"\n{'='*80}")
        print(f"All jobs completed or timeout reached")
        print(f"{'='*80}\n")

    def print_summary(self):
        """Print a summary of the stress test results"""
        if not self.results:
            print("\nNo results to summarize")
            return

        # Count job statuses
        succeeded = sum(1 for r in self.results.values() if r['status'] == 'Succeeded')
        failed = sum(1 for r in self.results.values() if r['status'] in ['Failed', 'Error'])
        running = sum(1 for r in self.results.values() if r['status'] == 'Running')
        stopped = sum(1 for r in self.results.values() if r['status'] == 'Stopped')
        other = len(self.results) - succeeded - failed - running - stopped

        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0

        print(f"\n{'='*80}")
        print(f"JIT PROXY SERVER STRESS TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Configuration:")
        print(f"  Project: {self.project}")
        print(f"  Command: {self.command}")
        print(f"\nResults:")
        print(f"  Jobs Requested: {self.num_jobs}")
        print(f"  Jobs Created: {len(self.job_ids)}")
        print(f"  Creation Failures: {len(self.creation_errors)}")
        print(f"  Test Duration: {duration:.1f}s")
        print(f"\nJob Execution Status:")
        print(f"  ✓ Succeeded: {succeeded:4d} ({succeeded/len(self.job_ids)*100:.1f}%)" if self.job_ids else "  ✓ Succeeded: 0")
        print(f"  ✗ Failed: {failed:4d} ({failed/len(self.job_ids)*100:.1f}%)" if self.job_ids else "  ✗ Failed: 0")
        print(f"  ⧗ Running: {running:4d} ({running/len(self.job_ids)*100:.1f}%)" if self.job_ids else "  ⧗ Running: 0")
        print(f"  ■ Stopped: {stopped:4d} ({stopped/len(self.job_ids)*100:.1f}%)" if self.job_ids else "  ■ Stopped: 0")
        if other > 0:
            print(f"  ? Other: {other:4d}")

        if len(self.job_ids) > 0:
            success_rate = (succeeded / len(self.job_ids)) * 100
            print(f"\nMetrics:")
            print(f"  Success Rate: {success_rate:.1f}%")

            if duration > 0:
                creation_throughput = len(self.job_ids) / duration
                print(f"  Job Creation Throughput: {creation_throughput:.2f} jobs/second")

                if succeeded > 0:
                    completion_throughput = succeeded / duration
                    print(f"  Job Completion Throughput: {completion_throughput:.2f} jobs/second")

        print(f"{'='*80}\n")

    def save_results(self, output_file: str):
        """Save detailed results to a JSON file"""
        result_data = {
            'test_config': {
                'project': self.project,
                'api_host': self.api_host,
                'num_jobs_requested': self.num_jobs,
                'num_jobs_created': len(self.job_ids),
                'num_creation_errors': len(self.creation_errors),
                'command': self.command,
                'hardware_tier_name': self.hardware_tier_name,
                'environment_id': self.environment_id,
                'timeout': self.timeout,
                'poll_interval': self.poll_interval,
            },
            'timing': {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else None
            },
            'jobs': self.results,
            'creation_errors': self.creation_errors
        }

        with open(output_file, 'w') as f:
            json.dump(result_data, f, indent=2)

        print(f"✓ Detailed results saved to: {output_file}\n")

    def run(self) -> bool:
        """
        Run the complete stress test

        Returns:
            True if test completed successfully, False otherwise
        """
        self.start_time = datetime.now()
        print(f"Starting stress test at {self.start_time.isoformat()}")

        # Create all jobs concurrently
        self.job_ids = self.create_jobs_concurrent()

        if not self.job_ids:
            print("✗ No jobs were created. Aborting test.")
            return False

        # Wait for completion if requested
        if self.wait_for_completion:
            self.wait_for_jobs()
        else:
            print("\n⚠ Skipping wait for job completion (--no-wait specified)")
            self.end_time = datetime.now()

        # Print summary
        self.print_summary()

        # Determine success
        if self.job_ids:
            success_count = sum(1 for r in self.results.values() if r['status'] == 'Succeeded')
            success_rate = success_count / len(self.job_ids)
            return success_rate >= 0.8  # 80% success threshold

        return False


def main():
    parser = argparse.ArgumentParser(
        description='Stress test the JIT proxy server by creating multiple Domino jobs concurrently',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test with 50 concurrent jobs
  python stress_test_jit.py --jobs 50 --project myuser/myproject

  # Custom AWS command to trigger JIT credentials
  python stress_test_jit.py --jobs 100 --project myuser/myproject \\
      --command "aws s3 ls && aws sts get-caller-identity"

  # High load test without waiting for completion
  python stress_test_jit.py --jobs 200 --project myuser/myproject --no-wait

  # Save results to file
  python stress_test_jit.py --jobs 50 --project myuser/myproject \\
      --output results.json

  # Specify hardware tier
  python stress_test_jit.py --jobs 50 --project myuser/myproject \\
      --hardware-tier "Small"

Environment Variables:
  DOMINO_API_HOST     - Required: Domino API endpoint (e.g., https://domino.company.com)
  DOMINO_USER_API_KEY - Required: Domino API key for authentication
        """
    )

    parser.add_argument(
        '--jobs', '-j',
        type=int,
        required=True,
        help='Number of jobs to create concurrently'
    )

    parser.add_argument(
        '--project', '-p',
        type=str,
        required=True,
        help='Domino project in owner/project-name format'
    )

    parser.add_argument(
        '--command', '-c',
        type=str,
        required=True,
        help='Command to run in each job (default: aws s3 ls)'
    )

    parser.add_argument(
        '--hardware-tier',
        '--hwtier',
        type=str,
        help='Hardware tier name to use for jobs',
        default="Small"
    )

    parser.add_argument(
        '--environment-id',
        type=str,
        help='Environment ID to use for jobs'
    )

    parser.add_argument(
        '--no-wait',
        action='store_true',
        help='Do not wait for jobs to complete'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=3600,
        help='Timeout in seconds when waiting for jobs (default: 3600s = 60 minutes)'
    )

    parser.add_argument(
        '--poll-interval',
        type=int,
        default=5,
        help='Seconds between job status polls (default: 5)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file for detailed results (JSON format)'
    )

    parser.add_argument(
        '--api-host',
        type=str,
        help='Domino API host (can also use DOMINO_API_HOST env var)'
    )

    parser.add_argument(
        '--api-key',
        type=str,
        help='Domino API key (can also use DOMINO_USER_API_KEY env var)'
    )

    args = parser.parse_args()

    # Get API credentials
    api_host = args.api_host or os.environ.get('DOMINO_API_HOST')
    api_key = args.api_key or os.environ.get('DOMINO_USER_API_KEY')

    if not api_host:
        print("Error: DOMINO_API_HOST environment variable or --api-host argument required")
        sys.exit(1)

    if not api_key:
        print("Error: DOMINO_USER_API_KEY environment variable or --api-key argument required")
        sys.exit(1)

    # Validate job count
    if args.jobs <= 0:
        print("Error: Number of jobs must be positive")
        sys.exit(1)

    if args.jobs > 1000:
        print(f"Warning: Creating {args.jobs} concurrent jobs may overwhelm the JIT proxy server and Domino cluster")
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted")
            sys.exit(0)
    
    if 'https://' not in api_host or 'http://' in api_host:
        api_host = 'https://' + api_host

    # Create and run stress test
    test = JitStressTest(
        api_host=api_host,
        api_key=api_key,
        project=args.project,
        num_jobs=args.jobs,
        command=args.command,
        hardware_tier_name=args.hardware_tier,
        environment_id=args.environment_id,
        wait_for_completion=not args.no_wait,
        timeout=args.timeout,
        poll_interval=args.poll_interval
    )

    success = test.run()

    # Save results if requested
    if args.output:
        test.save_results(args.output)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
