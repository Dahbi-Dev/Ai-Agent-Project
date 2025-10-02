import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# Store results between commands
last_search = []
current_email = None
current_recipients = []

#-- Load JSON file
def load_file(name):
    file = Path(f"data/{name}")
    if not file.exists():
        file.parent.mkdir(exist_ok=True)
        with open(file, 'w') as f:
            json.dump({}, f)
        return {}
    with open(file) as f:
        return json.load(f)

#-- Save JSON file
def save_file(name, data):
    Path("data").mkdir(exist_ok=True)
    with open(f"data/{name}", 'w') as f:
        json.dump(data, f, indent=2)

#-- Parse user query into filters
def parse_query(text):
    text = text.lower()
    
    #-- Find skills
    skills = []
    for skill in ["react", "python", "javascript", "django", "node.js", "html", "css", "sql", "git"]:
        if skill in text:
            skills.append(skill.title())
    
    #-- Find location
    location = None
    for city in ["casablanca", "rabat", "marrakech", "fes"]:
        if city in text:
            location = city.title()
            break
    
    #-- Find experience range
    exp_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', text)
    min_exp = int(exp_match.group(1)) if exp_match else 0
    max_exp = int(exp_match.group(2)) if exp_match else 10

    #-- Find availability
    days = 30 if "this month" in text else 45
    
    return {"skills": skills, "location": location, "minExp": min_exp, "maxExp": max_exp, "days": days}

#-- Search and score candidates
def search_candidates(filters):
    global last_search
    candidates = load_file("candidates.json")
    results = []
    
    for person in candidates:
        score = 0
        reasons = []
        
        #-- Score skills (+2 each)
        if filters["skills"]:
            matches = set(person["skills"]) & set(filters["skills"])
            if matches:
                points = len(matches) * 2
                score += points
                reasons.append(f"{'+'.join(matches)} (+{points})")
        
        #-- Score location (+1)
        if filters["location"] and person["location"] == filters["location"]:
            score += 1
            reasons.append(f"{person['location']} (+1)")
        
        #-- Score experience (+1)
        if filters["minExp"] - 1 <= person["experienceYears"] <= filters["maxExp"] + 1:
            score += 1
            reasons.append(f"{person['experienceYears']}y (+1)")
        
        #-- Score availability (+1)
        avail = datetime.strptime(person["availabilityDate"], "%Y-%m-%d")
        if avail <= datetime.today() + timedelta(days=filters["days"]):
            score += 1
            reasons.append("Available (+1)")
        
        results.append({"person": person, "score": score, "reason": ", ".join(reasons) + f" = {score} pts"})
    
    last_search = sorted(results, key=lambda x: x["score"], reverse=True)[:5]
    return last_search

#-- Save shortlist
def save_shortlist(name, numbers):
    if not last_search:
        return "Error: No search results"
    
    favorites = [last_search[n-1]["person"] for n in numbers if 1 <= n <= len(last_search)]
    all_lists = load_file("shortlists.json")
    all_lists[name] = favorites
    save_file("shortlists.json", all_lists)
    return f"Saved {len(favorites)} candidates to '{name}'"

#-- Get shortlist
def get_shortlist(name):
    return load_file("shortlists.json").get(name, [])

#-- Create email
def draft_email(people, job_name):
    jobs = load_file("jobs.json")
    job = next((j for j in jobs if j["title"] == job_name), None)
    
    subject = f"Exciting {job_name} opportunity!"
    
    if len(people) == 1:
        text = f"Hi {people[0]['firstName']},\n\n"
    else:
        text = "Hi there,\n\n"
    
    text += f"We think you'd be a great fit for our {job_name} role"
    
    if job:
        text += f" in {job['location']}.\n\n{job['jdSnippet']}\n\n"
        text += f"Skills needed: {', '.join(job['skillsRequired'])}.\n\n"
    else:
        text += ".\n\n"
    
    text += "Would you like to chat this week?"
    
    return {"subject": subject, "text": text}

#-- Create HTML email
def html_template(email):
    return f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial; color: #333; }}
        .container {{ max-width: 600px; margin: 20px auto; padding: 20px; }}
        h2 {{ color: #2c3e50; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>{email['subject']}</h2>
        <p style="white-space: pre-line;">{email['text']}</p>
        <p>Best regards,<br/>HR Team</p>
    </div>
</body>
</html>"""

#-- Get analytics
def analytics_summary():
    candidates = load_file("candidates.json")
    stages = Counter([c["stage"] for c in candidates])
    all_skills = [skill for c in candidates for skill in c["skills"]]
    top_skills = Counter(all_skills).most_common(3)
    return {"stages": dict(stages), "skills": top_skills}
def handle_search(cmd):
    print("\nSearching...\n")
    filters = parse_query(cmd)
    results = search_candidates(filters)
    
    for i, r in enumerate(results, 1):
        p = r['person']
        print(f"#{i}: {p['firstName']} {p['lastName']}")
        print(f"    {p['email']}")
        print(f"    {p['location']} | {p['experienceYears']} years | {', '.join(p['skills'])}")
        print(f"    Available: {p['availabilityDate']} | Stage: {p['stage']}")
        print(f"    Score: {r['reason']}\n")

#-- Handle save command
def handle_save(cmd):
    numbers = [int(n) for n in re.findall(r'#(\d+)', cmd)]
    name_match = re.search(r'as\s+["\']?([^"\']+)["\']?', cmd)
    
    if numbers and name_match:
        result = save_shortlist(name_match.group(1).strip(), numbers)
        print(f"\n{result}\n")
    else:
        print("\nFormat: Save #1 #3 as \"Name\"\n")

#-- Handle draft command
def handle_draft(cmd):
    global current_email, current_recipients
    
    list_match = re.search(r'for\s+["\']([^"\']+)["\']', cmd)
    job_match = re.search(r'job\s+["\']([^"\']+)["\']', cmd)
    
    if not list_match:
        print("\nFormat: Draft email for \"List-Name\" using job \"Job-Name\"\n")
        return
    
    people = get_shortlist(list_match.group(1))
    if not people:
        print(f"\nShortlist not found\n")
        return
    
    job_name = job_match.group(1) if job_match else "a position"
    current_recipients = people
    current_email = draft_email(people, job_name)
    
    names = ', '.join([f"{p['firstName']} {p['lastName']}" for p in people])
    print(f"\nEMAIL PREVIEW (Plain Text)\n")
    print(f"To: {names}")
    print(f"Subject: {current_email['subject']}\n")
    print(current_email['text'])
    print("\nBest regards,\nHR Team\n")
    
    #-- Show HTML version
    html = html_template(current_email)
    print("\nHTML VERSION:\n")
    print(html)
    print()
    
    print("Type 'Change subject to \"new subject\"' to edit\n")

#-- Handle edit command
def handle_edit(cmd):
    if not current_email:
        print("\nNo email to edit\n")
        return
    
    if "subject" in cmd.lower():
        match = re.search(r'to\s+["\']([^"\']+)["\']', cmd)
        if match:
            current_email['subject'] = match.group(1)
            print(f"\nSubject updated to: {current_email['subject']}\n")
            print(f"Subject: {current_email['subject']}\n{current_email['text']}\n")

#-- Handle analytics command
def handle_analytics():
    stats = analytics_summary()
    print("\nANALYTICS\n")
    print("Pipeline by stage:")
    for stage, count in stats['stages'].items():
        print(f"  {stage}: {count}")
    print("\nTop skills:")
    for skill, count in stats['skills']:
        print(f"  {skill}: {count}")
    print()

#-- Main program
def main():
    print("\nHR AGENT - Candidate Search & Outreach Assistant")
    print("\nAvailable Commands:")
    print("  Find React interns in Casablanca, 0-2 years")
    print("  Save #1 #3 as \"List-Name\"")
    print("  Draft email for \"List-Name\" using job \"Job Name\"")
    print("  Change subject to \"New Subject\"")
    print("  Show analytics")
    print("  quit")
    print()
    
    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            
            lower = cmd.lower()
            
            if lower in ["quit", "exit"]:
                print("Goodbye!\n")
                break
            elif any(w in lower for w in ["find", "search"]):
                handle_search(cmd)
            elif "save" in lower:
                handle_save(cmd)
            elif "draft" in lower or "email" in lower:
                handle_draft(cmd)
            elif "change" in lower or "edit" in lower:
                handle_edit(cmd)
            elif "analytics" in lower or "stats" in lower:
                handle_analytics()
            else:
                print("Unknown command. See available commands above.\n")
        
        except KeyboardInterrupt:
            print("\nGoodbye!\n")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()