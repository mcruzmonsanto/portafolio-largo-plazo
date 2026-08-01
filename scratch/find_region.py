import psycopg2
import concurrent.futures

password = '9R%2Akf%3F-QPxqHjPK'
project_ref = 'tbwxttkszyozjgframvr'
regions = [
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-west-1', 'eu-west-2', 'eu-central-1', 
    'ap-south-1', 'ap-southeast-1', 'ap-southeast-2',
    'ap-northeast-1', 'ap-northeast-2',
    'sa-east-1', 'ca-central-1'
]

def test_region(region):
    url = f'postgresql://postgres.{project_ref}:{password}@aws-0-{region}.pooler.supabase.com:6543/postgres'
    try:
        conn = psycopg2.connect(url, connect_timeout=3)
        conn.close()
        return (region, True, "Success")
    except Exception as e:
        return (region, False, str(e))

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(test_region, regions)
    
found = False
for region, success, error in results:
    if success:
        print(f'✅ FOUND IT! The region is: {region}')
        found = True
        break

if not found:
    print('❌ Could not find the correct region automatically.')
