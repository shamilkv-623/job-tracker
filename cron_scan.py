import os
from supabase import create_client

# 1. Setup Connection (using Environment Variables for security)
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") # Use Service Role for backend access
supabase = create_client(url, key)

def run_global_scan():
    # 2. Fetch ALL users who have active monitoring
    # Assuming your table is called 'user_settings'
    users = supabase.table("user_settings").select("user_id, keywords, urls").execute()

    for user in users.data:
        user_id = user['user_id']
        keywords = user['keywords']
        urls = user['urls']
        
        print(f"Scanning for User: {user_id}...")
        
        # 3. Run your existing scraping logic here
        results = your_scraper_function(urls, keywords)
        
        # 4. Save results back to a 'scans' table for that user
        supabase.table("scan_results").insert({
            "user_id": user_id,
            "found_jobs": results,
            "status": "completed"
        }).execute()

if __name__ == "__main__":
    run_global_scan()
