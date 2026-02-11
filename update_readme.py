#!/usr/bin/env python3

import os
import sys
import requests
import time
from datetime import datetime
from collections import defaultdict

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_USERNAME = os.environ.get('GITHUB_USERNAME')
REQUEST_TIMEOUT = 10

def fetch_pull_requests():
    if not GITHUB_TOKEN:
        print("WARNING: GITHUB_TOKEN not set. Using unauthenticated requests (60 req/hr limit)")
    
    if not GITHUB_USERNAME:
        print("ERROR: GITHUB_USERNAME environment variable is required")
        sys.exit(1)
    
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    
    url = f'https://api.github.com/search/issues?q=author:{GITHUB_USERNAME}+type:pr&per_page=100&sort=created&order=desc'
    
    all_prs = []
    page = 1
    
    while True:
        try:
            response = requests.get(f"{url}&page={page}", headers=headers, timeout=REQUEST_TIMEOUT)
            
            remaining = response.headers.get('X-RateLimit-Remaining', '?')
            limit = response.headers.get('X-RateLimit-Limit', '?')
            
            if remaining != '?':
                print(f"Rate limit: {remaining}/{limit} remaining")
            
            if response.status_code == 403 and remaining == '0':
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(0, reset_time - int(time.time()))
                print(f"ERROR: Rate limited! Try again in {wait_time} seconds")
                sys.exit(1)
            
            if response.status_code != 200:
                print(f"ERROR: API Error: HTTP {response.status_code}")
                if response.status_code == 401:
                    print("ERROR: Invalid or expired GitHub token")
                elif response.status_code == 422:
                    print("ERROR: Invalid search query")
                sys.exit(1)
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                break
                
            all_prs.extend(items)
            
            if len(items) < 100:
                break
            
            page += 1
            
        except requests.Timeout:
            print(f"ERROR: Request timeout after {REQUEST_TIMEOUT}s. Please try again.")
            sys.exit(1)
        except requests.RequestException as e:
            print(f"ERROR: Network error: {e}")
            sys.exit(1)
    
    return all_prs

def group_by_repo(prs):
    repos = defaultdict(list)
    
    for pr in prs:
        repo_url = pr['repository_url']
        repo_name = repo_url.replace('https://api.github.com/repos/', '')
        
        if '/' not in repo_name:
            print(f"WARNING: Skipping malformed repo: {repo_name}")
            continue
        
        org_name = repo_name.split('/', 1)[0]
        
        if org_name.lower() == GITHUB_USERNAME.lower():
            continue
        
        is_merged = pr.get('pull_request', {}).get('merged_at') is not None
        is_open = pr['state'] == 'open'
        
        if not (is_open or is_merged):
            continue
        
        repos[repo_name].append({
            'number': pr['number'],
            'title': pr['title'],
            'state': pr['state'],
            'url': pr['html_url'],
            'created_at': pr['created_at'],
            'merged': is_merged
        })
    
    return repos

def escape_markdown_cell(text):
    if not text:
        return ""
    text = str(text)
    text = text.replace('|', '\\|')
    text = text.replace('\n', ' ').replace('\r', '')
    return text

def generate_markdown(repos):
    markdown = []
    
    if not repos:
        markdown.append("**Total Contributions:** 0 PRs\n")
        markdown.append("No contributions found yet!")
        return '\n'.join(markdown)
    
    sorted_repos = sorted(
        repos.items(), 
        key=lambda x: max(pr['number'] for pr in x[1]), 
        reverse=True
    )
    
    total_prs = sum(len(prs) for prs in repos.values())
    merged_prs = sum(1 for prs in repos.values() for pr in prs if pr['merged'])
    
    markdown.append(f"**Total Contributions:** {total_prs} PRs across {len(repos)} projects | **Merged:** {merged_prs} PRs\n")
    markdown.append("")
    
    for repo_name, prs in sorted_repos:
        org_name, project_name = repo_name.split('/', 1)
        
        markdown.append(f"### [{project_name}](https://github.com/{repo_name})")
        markdown.append("")
        markdown.append("| # | PR | Status |")
        markdown.append("|---|---|--------|")
        
        sorted_prs = sorted(prs, key=lambda x: x['number'], reverse=True)
        
        for pr in sorted_prs:
            if pr['merged']:
                status = "Merged"
            elif pr['state'] == 'open':
                status = "Open"
            else:
                status = "Unknown"
            
            safe_title = escape_markdown_cell(pr['title'])
            markdown.append(f"| #{pr['number']} | [{safe_title}]({pr['url']}) | {status} |")
        
        markdown.append("")
    
    return '\n'.join(markdown)

def update_readme(content):
    readme_path = 'README.md'
    start_marker = "<!-- OSS_CONTRIBUTIONS_START -->"
    end_marker = "<!-- OSS_CONTRIBUTIONS_END -->"
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    if os.path.exists(readme_path):
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                readme = f.read()
        except (IOError, OSError) as e:
            print(f"ERROR: Could not read README.md: {e}")
            sys.exit(1)
        except UnicodeDecodeError:
            print("ERROR: README.md encoding is not UTF-8")
            sys.exit(1)
    else:
        readme = f"""# My Open Source Contributions

{start_marker}
{end_marker}

---
*This README is automatically updated via GitHub Actions*
"""
    
    if start_marker not in readme or end_marker not in readme:
        print("ERROR: Required markers not found in README.md!")
        sys.exit(1)
    
    start_idx = readme.find(start_marker) + len(start_marker)
    end_idx = readme.find(end_marker)
    
    new_readme = readme[:start_idx] + "\n" + content + "\n" + readme[end_idx:]
    
    timestamp_start = new_readme.find('<!-- TIMESTAMP -->')
    timestamp_end = new_readme.find('<!-- TIMESTAMP -->', timestamp_start + 1)
    if timestamp_start != -1 and timestamp_end != -1:
        new_readme = new_readme[:timestamp_start + 18] + timestamp + new_readme[timestamp_end:]
    
    try:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(new_readme)
    except (IOError, OSError) as e:
        print(f"ERROR: Could not write README.md: {e}")
        sys.exit(1)
    
    print("README.md updated successfully!")

def main():
    print("Fetching OSS contributions...")
    prs = fetch_pull_requests()
    print(f"Found {len(prs)} total pull requests")
    
    print("Grouping by repository...")
    repos = group_by_repo(prs)
    print(f"Contributions to {len(repos)} external projects")
    
    print("Generating markdown...")
    markdown = generate_markdown(repos)
    
    print("Updating README...")
    update_readme(markdown)
    
    print("Done!")

if __name__ == '__main__':
    main()
