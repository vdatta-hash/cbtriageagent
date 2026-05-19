#!/usr/bin/env python3
"""
triage.py - Core wrapper for the corporate Buganizer CLI (issues-cli).
Handles secure execution of 'issues' commands with strict parameter validations.
"""

import json
import logging
import subprocess
import re
import urllib.request
import urllib.error
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Standard Buganizer CLI binary path on the remote VM
ISSUES_CLI_PATH = "/google/bin/releases/issues-cli/issues"

# Regex to validate simple search query (alphanumeric, spaces, dashes, underscores)
SAFE_QUERY_REGEX = re.compile(r"^[a-zA-Z0-9\s\-_:\(\)\[\]\.]+$")

def validate_bug_id(bug_id):
    """
    Validates that a bug ID is a pure positive integer.
    Returns the integer value if valid, otherwise raises ValueError.
    """
    if isinstance(bug_id, int):
        if bug_id <= 0:
            raise ValueError("Bug ID must be a positive integer.")
        return bug_id
        
    s = str(bug_id).strip()
    if not s.isdigit():
        raise ValueError(f"Invalid Bug ID: '{bug_id}'. Must be numeric.")
        
    val = int(s)
    if val <= 0:
        raise ValueError("Bug ID must be a positive integer.")
    return val

def validate_query(query):
    """
    Validates a search query or text input to prevent command injections.
    Returns the query if safe, otherwise raises ValueError.
    """
    if not query:
        raise ValueError("Query cannot be empty.")
    s = str(query).strip()
    if not SAFE_QUERY_REGEX.match(s):
        raise ValueError("Query contains unsafe characters. Only letters, numbers, spaces, and basic symbols are allowed.")
    return s

def run_issues_command(cmd_args):
    """
    Executes the issues-cli binary securely using parameterized arguments.
    Never uses shell=True.
    Returns the JSON or string output.
    """
    # Ensure binary path is the first parameter
    full_command = [ISSUES_CLI_PATH] + cmd_args
    
    logging.info("Executing command securely: %s", " ".join(full_command))
    
    try:
        result = subprocess.run(
            full_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False # Do not throw automatically so we can parse stderr
        )
        
        if result.returncode != 0:
            # Standardize and safely report execution errors
            err_msg = result.stderr.strip() if result.stderr else "Unknown CLI error."
            logging.error("CLI Execution failed: %s", err_msg)
            
            # Specific check for expired credentials
            if "Required key not available" in err_msg or "expired" in err_msg.lower() or "ssourl" in err_msg.lower():
                raise PermissionError("Buganizer authentication expired. Please run 'gcert' on the VM.")
            
            raise RuntimeError(f"Buganizer CLI error: {err_msg}")
            
        return result.stdout.strip()
        
    except FileNotFoundError:
        logging.error("Buganizer CLI binary not found at: %s", ISSUES_CLI_PATH)
        raise RuntimeError(f"Buganizer CLI binary not found at '{ISSUES_CLI_PATH}'.")

def call_buganizer_rest_api(endpoint_path, query_params=None, method="GET", body=None, auth_token=None):
    """
    Makes a secure HTTPS request to the corporate Buganizer REST API.
    Uses only standard library components to prevent dependency pollution.
    """
    if not auth_token:
        raise PermissionError("Authentication token required to call Buganizer REST API.")
        
    base_url = "https://issuetracker.googleapis.com/v1"
    url = f"{base_url}{endpoint_path}"
    
    if query_params:
        encoded_params = urllib.parse.urlencode(query_params)
        url = f"{url}?{encoded_params}"
        
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {auth_token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    
    if body:
        req.data = json.dumps(body).encode("utf-8")
        
    try:
        logging.info("Calling Buganizer REST API: %s %s", method, url)
        with urllib.request.urlopen(req, timeout=10) as response:
            raw_response = response.read().decode("utf-8")
            return json.loads(raw_response)
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8") if he.fp else ""
        logging.error("REST API HTTP Error (%d): %s. Details: %s", he.code, he.reason, err_body)
        if he.code == 401:
            raise PermissionError("OAuth/Gaia authentication token expired or invalid.")
        raise RuntimeError(f"Buganizer REST API error: {he.code} {he.reason}")
    except Exception as e:
        logging.exception("Failed to call Buganizer REST API:")
        raise RuntimeError(f"Failed to reach Buganizer REST API: {e}")

def get_bug_details(bug_id, auth_token=None):
    """
    Fetches full details of a specific Buganizer issue.
    """
    validated_id = validate_bug_id(bug_id)
    if auth_token:
        return call_buganizer_rest_api(f"/issues/{validated_id}", auth_token=auth_token)
        
    # Fallback to local issues-cli
    raw_output = run_issues_command(["show", str(validated_id), "--format=json"])
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        # If not JSON, return raw output string
        return {"raw_text": raw_output}

def list_bugs(query, limit=50, auth_token=None):
    """
    Lists Buganizer issues matching a specific query.
    """
    validated_query = validate_query(query)
    
    # Limit limits output count
    limit = min(max(int(limit), 1), 200)
    
    if auth_token:
        return call_buganizer_rest_api(
            "/issues",
            query_params={"query": validated_query, "pageSize": limit},
            auth_token=auth_token
        )
        
    # Fallback to local issues-cli
    raw_output = run_issues_command([
        "list", 
        validated_query, 
        "--format=json", 
        f"--limit={limit}"
    ])
    
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        # Parse lines or return structured raw
        return {"raw_text": raw_output}

if __name__ == "__main__":
    # Simple local command line helper for standalone manual testing
    import sys
    if len(sys.argv) < 2:
        print("Usage: triage.py <command> [args]")
        sys.exit(1)
        
    command = sys.argv[1]
    try:
        if command == "show" and len(sys.argv) == 3:
            print(json.dumps(get_bug_details(sys.argv[2]), indent=2))
        elif command == "list" and len(sys.argv) == 3:
            print(json.dumps(list_bugs(sys.argv[2]), indent=2))
        else:
            print("Invalid standalone arguments.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
