#!/usr/bin/env python3
"""
server.py - Zero-dependency lightweight HTTP server for the Gemini Buganizer Agent.
Uses only standard Python libraries to eliminate external package supply-chain risks.
"""

import http.server
import urllib.parse
import json
import logging
import sys
import os
import argparse

# Import our secure Buganizer CLI wrapper
import triage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class SecureAgentRequestHandler(http.server.BaseHTTPRequestHandler):
    """
    Custom Request Handler enforcing strict secure API routing, input
    validations, and fail-close error handling.
    """
    
    def log_message(self, format, *args):
        # Redirect default http.server stderr logs to standard logging
        logging.info("%s - %s" % (self.address_string(), format%args))

    def send_json_response(self, status_code, data):
        """
        Sends a secure JSON response with standard security headers.
        """
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        # Anti-clickjacking & MIME-sniffing guards
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def send_error_response(self, status_code, message):
        """
        Ensures secure error handling by obscuring raw stack traces from the caller.
        """
        self.send_json_response(status_code, {
            "error": message,
            "status": status_code
        })

    def do_GET(self):
        """
        Routes GET requests securely.
        """
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        try:
            # 1. Serve OpenAPI YAML Descriptor
            if path == "/openapi.yaml":
                yaml_path = os.path.join(os.path.dirname(__file__), "openapi.yaml")
                if not os.path.exists(yaml_path):
                    self.send_error_response(404, "OpenAPI specification file not found.")
                    return
                    
                self.send_response(200)
                self.send_header("Content-Type", "application/x-yaml")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
                
                with open(yaml_path, "rb") as f:
                    self.wfile.write(f.read())
                return
                
            # 2. Route GET /issues (Search issues)
            if path == "/issues":
                if "query" not in query_params:
                    self.send_error_response(400, "Missing required query parameter 'query'.")
                    return
                    
                raw_query = query_params["query"][0]
                limit = 50
                if "limit" in query_params:
                    try:
                        limit = int(query_params["limit"][0])
                    except ValueError:
                        self.send_error_response(400, "Parameter 'limit' must be an integer.")
                        return
                        
                # List issues securely
                results = triage.list_bugs(raw_query, limit=limit)
                self.send_json_response(200, results)
                return
                
            # 3. Route GET /issues/{bug_id} (Get single issue details)
            if path.startswith("/issues/"):
                parts = path.split("/")
                # Expected: ["", "issues", "{bug_id}"]
                if len(parts) == 3 and parts[1] == "issues":
                    raw_bug_id = parts[2]
                    try:
                        bug_id = triage.validate_bug_id(raw_bug_id)
                    except ValueError as ve:
                        self.send_error_response(400, str(ve))
                        return
                        
                    # Fetch details securely
                    details = triage.get_bug_details(bug_id)
                    self.send_json_response(200, details)
                    return

            # If path matches nothing
            self.send_error_response(404, "Endpoint not found.")
            
        except PermissionError as pe:
            logging.error("Permission/Auth error: %s", pe)
            self.send_error_response(401, str(pe))
        except Exception as e:
            logging.exception("Internal system failure during GET:")
            self.send_error_response(500, "Internal system error. CLI execution failed.")

    def do_POST(self):
        """
        Routes POST requests securely.
        """
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        try:
            # 1. Route POST /issues/{bug_id}/triage
            if path.startswith("/issues/") and path.endswith("/triage"):
                parts = path.split("/")
                # Expected: ["", "issues", "{bug_id}", "triage"]
                if len(parts) == 4 and parts[1] == "issues" and parts[3] == "triage":
                    raw_bug_id = parts[2]
                    try:
                        bug_id = triage.validate_bug_id(raw_bug_id)
                    except ValueError as ve:
                        self.send_error_response(400, str(ve))
                        return
                    
                    # Placeholder for automated triage logic once shared.
                    # Currently runs analysis simulation.
                    logging.info("Triggering automated triage simulation on Bug %d...", bug_id)
                    
                    # Fetch current bug details to evaluate
                    details = triage.get_bug_details(bug_id)
                    
                    title = details.get("title", "").lower()
                    description = details.get("description", "").lower()
                    
                    # Simple mock triage rule execution
                    action_taken = "NO_ACTION"
                    decision = "PENDING_REVIEW"
                    notes = "Analyzed blocker issue. Awaiting triage rules document from user."
                    
                    if "blocker" in title or "blocker" in description:
                        action_taken = "FLAGGED_BLOCKER"
                        decision = "PRIORITY_TRIAGE"
                        notes = "Flagged as high-priority blocker based on title analysis."
                        
                    triage_result = {
                        "bug_id": bug_id,
                        "action_taken": action_taken,
                        "decision": decision,
                        "notes": notes,
                        "raw_details": {
                            "title": details.get("title", "Unknown"),
                            "status": details.get("status", "New")
                        }
                    }
                    
                    self.send_json_response(200, triage_result)
                    return
                    
            # If no endpoints match
            self.send_error_response(404, "Endpoint not found.")
            
        except PermissionError as pe:
            logging.error("Permission/Auth error: %s", pe)
            self.send_error_response(401, str(pe))
        except Exception as e:
            logging.exception("Internal system failure during POST:")
            self.send_error_response(500, "Internal system error. CLI execution failed.")

def run_server(host, port):
    """
    Starts the secure HTTP web server.
    """
    server_address = (host, port)
    try:
        httpd = http.server.HTTPServer(server_address, SecureAgentRequestHandler)
        logging.info("Agent Server successfully running at http://%s:%d", host, port)
        logging.info("OpenAPI Spec served at http://%s:%d/openapi.yaml", host, port)
        httpd.serve_forever()
    except Exception as e:
        logging.critical("Could not start server: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini Enterprise Buganizer Agent Web Server")
    # Enforce secure default host listening on localhost (127.0.0.1) as required by guidelines
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port number to bind to")
    
    args = parser.parse_args()
    run_server(args.host, args.port)
