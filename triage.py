#!/usr/bin/env python3
"""
triage.py - Core wrapper for the corporate Buganizer CLI (issues-cli).
Handles secure execution of 'issues' commands with strict parameter validations.
Now fully upgraded to use Gemini-based system instructions for smart triage recommendations.
"""

import json
import logging
import subprocess
import re
import urllib.request
import urllib.error
import urllib.parse
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

# Configuration for the Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAu2OmgvF8kEDjSZ_WozMX3HDyKBZpeyDo")
PLAYBOOK_PATH = "/Users/vdatta/.gemini/jetski/scratch/buganizer_triage_playbook_8186342.md"

class TriageRecommendation(BaseModel):
    action_taken: str = Field(description="The high-level action category: DUPLICATE, ROUTE_ONCALL, WORKAROUND, RECOMMEND_CR, NEED_INFO, or NO_ACTION")
    decision: str = Field(description="The overall triage decision, e.g. TRIAGED, DUPLICATE_CLOSED, WAITING_INFO")
    notes: str = Field(description="Detailed justification and triage comments explaining the reasoning based on the playbook")
    actions_detail: List[str] = Field(description="Step-by-step recommended actions based on the playbook phases")
    recommended_assignee: Optional[str] = Field(description="Recommended PM LDAP or oncall team email (e.g. modelarmor-oncall@google.com) if reassignment is needed")
    recommended_hotlist_updates: Optional[List[str]] = Field(description="List of hotlist actions: e.g. ['ADD:8278523', 'REMOVE:8186342']")
    comment_to_post: Optional[str] = Field(description="The exact markdown comment text to be posted on the Buganizer ticket")


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

def update_bug(bug_id, update_fields, comment_text=None, auth_token=None):
    """
    Updates a specific Buganizer issue. Supports updating status, custom fields,
    assignees, and adding comments.
    """
    validated_id = validate_bug_id(bug_id)
    
    if auth_token:
        # 1. Perform issue patch for fields (e.g., status, assignee, custom fields)
        if update_fields:
            call_buganizer_rest_api(
                f"/issues/{validated_id}",
                method="PATCH",
                body=update_fields,
                auth_token=auth_token
            )
        # 2. Post comment if provided
        if comment_text:
            call_buganizer_rest_api(
                f"/issues/{validated_id}/comments",
                method="POST",
                body={"comment": comment_text},
                auth_token=auth_token
            )
        return {"status": "SUCCESS", "bug_id": validated_id}
        
    # Fallback to local issues-cli
    cli_args = ["update", str(validated_id)]
    if update_fields and "status" in update_fields:
        cli_args += [f"--status={update_fields['status']}"]
    if update_fields and "assignee" in update_fields:
        cli_args += [f"--assignee={update_fields['assignee']}"]
    if comment_text:
        cli_args += [f"--comment={comment_text}"]
        
    raw_output = run_issues_command(cli_args)
    return {"status": "SUCCESS", "bug_id": validated_id, "raw_text": raw_output}

def update_bug_hotlist(bug_id, hotlist_id, action="ADD", auth_token=None):
    """
    Adds or removes a hotlist from a Buganizer issue.
    """
    validated_id = validate_bug_id(bug_id)
    validated_hotlist = validate_bug_id(hotlist_id)
    
    if auth_token:
        method = "POST" if action == "ADD" else "DELETE"
        return call_buganizer_rest_api(
            f"/issues/{validated_id}/hotlists/{validated_hotlist}",
            method=method,
            auth_token=auth_token
        )
        
    # Fallback to local issues-cli
    cmd = "add-hotlist" if action == "ADD" else "remove-hotlist"
    raw_output = run_issues_command([cmd, str(validated_id), str(validated_hotlist)])
    return {"status": "SUCCESS", "raw_text": raw_output}

def triage_issue(bug_id, auth_token=None, recommend_only=False):
    """
    Executes the 5-phase triage process utilizing Gemini models configured with 
    the custom Playbook as system instructions to generate optimal triage actions.
    """
    validated_id = validate_bug_id(bug_id)
    logging.info("Running AI-driven Playbook Triage on Bug %d (recommend_only=%s)...", validated_id, recommend_only)
    
    # Step 1: Fetch bug details from Buganizer
    details = get_bug_details(validated_id, auth_token=auth_token)
    
    # Step 2: Load the playbook system instructions
    if not os.path.exists(PLAYBOOK_PATH):
        raise FileNotFoundError(f"Triage Playbook markdown file not found at: '{PLAYBOOK_PATH}'")
    
    with open(PLAYBOOK_PATH, "r", encoding="utf-8") as f:
        playbook_content = f.read()
        
    # Step 3: Initialize the Gemini client and generate the structured triage recommendation
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"You are the NPS-GE-Security Bug Triage Agent. Triage the following issue "
        f"based strictly on your system instructions playbook. Return your recommendation "
        f"in the requested structured JSON format:\n\n"
        f"{json.dumps(details, indent=2)}"
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=playbook_content,
                response_mime_type="application/json",
                response_schema=TriageRecommendation,
                temperature=0.1, # low temperature for high consistency with policies
            )
        )
        # Parse structured recommendation
        rec = json.loads(response.text)
    except Exception as e:
        logging.exception("Gemini content generation failed:")
        raise RuntimeError(f"Failed to generate triage recommendation using Gemini model: {e}")
        
    # If user requested recommendations only, return them immediately without making changes
    if recommend_only:
        logging.info("Recommend-only execution complete for Bug %d.", validated_id)
        return {
            "bug_id": validated_id,
            "execute_changes": False,
            "recommendation": rec
        }
        
    # Step 4: Execute recommended changes on Buganizer if execute_changes is True
    actions_taken = []
    
    # Action A: Post Comment
    comment_text = rec.get("comment_to_post")
    
    # Action B: Update Fields (Status & Assignee)
    update_fields = {}
    if rec.get("action_taken") == "DUPLICATE":
        update_fields["status"] = "DUPLICATE"
        
    recommended_assignee = rec.get("recommended_assignee")
    if recommended_assignee:
        update_fields["assignee"] = recommended_assignee
        
    # Perform the update
    if update_fields or comment_text:
        try:
            update_bug(validated_id, update_fields, comment_text=comment_text, auth_token=auth_token)
            actions_taken.append(f"Applied updates: {json.dumps(update_fields)}")
            if comment_text:
                actions_taken.append("Posted automated comment notification.")
        except Exception as e:
            logging.error("Failed to apply bug updates: %s", e)
            
    # Action C: Perform Hotlist Transitions
    hotlist_updates = rec.get("recommended_hotlist_updates") or []
    for transition in hotlist_updates:
        try:
            parts = transition.split(":")
            if len(parts) == 2:
                action = parts[0].strip().upper() # ADD / REMOVE
                target_hotlist = int(parts[1].strip())
                update_bug_hotlist(validated_id, target_hotlist, action=action, auth_token=auth_token)
                actions_taken.append(f"Executed Hotlist {action} for {target_hotlist}")
        except Exception as e:
            logging.error("Failed to execute hotlist transition '%s': %s", transition, e)
            
    # Final completion comment confirmation
    final_notes = f"Triage changes successfully applied based on Gemini recommendation: " + "; ".join(actions_taken)
    try:
        update_bug(
            validated_id,
            {},
            comment_text=f"NPS-GE-Security AI Triage complete. Rationale:\n{rec.get('notes')}",
            auth_token=auth_token
        )
    except Exception as e:
         logging.error("Failed to post final completion comment: %s", e)
         
    return {
        "bug_id": validated_id,
        "execute_changes": True,
        "gemini_recommendation": rec,
        "actions_executed": actions_taken,
        "status": "SUCCESS"
    }

if __name__ == "__main__":
    # Simple local command line helper for standalone manual testing
    import sys
    if len(sys.argv) < 2:
        print("Usage: triage.py <command> [args]")
        print("  show <bug_id>            : Show bug details")
        print("  list <query>             : Search bugs")
        print("  triage <bug_id>          : Run 5-phase triage process locally")
        sys.exit(1)
        
    command = sys.argv[1]
    try:
        if command == "show" and len(sys.argv) == 3:
            print(json.dumps(get_bug_details(sys.argv[2]), indent=2))
        elif command == "list" and len(sys.argv) == 3:
            print(json.dumps(list_bugs(sys.argv[2]), indent=2))
        elif command == "triage" and len(sys.argv) == 3:
            print(json.dumps(triage_issue(sys.argv[2]), indent=2))
        else:
            print("Invalid standalone arguments.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
