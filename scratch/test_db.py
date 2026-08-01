import streamlit as st
import psycopg2

password = st.secrets['connections']['supabase']['url'].split(':')[2].split('@')[0]
project_ref = 'tbwxttkszyozjgframvr'

urls_to_test = [
    f'postgresql://postgres.{project_ref}:{password}@aws-0-us-east-1.pooler.supabase.com:6543/postgres',
    f'postgresql://postgres:{password}@aws-0-us-east-1.pooler.supabase.com:6543/postgres',
    f'postgresql://postgres:{password}@{project_ref}.pooler.supabase.com:6543/postgres',
    f'postgresql://postgres.{project_ref}:{password}@{project_ref}.pooler.supabase.com:6543/postgres'
]

for url in urls_to_test:
    host = url.split('@')[1]
    user = url.split(':')[1].replace('//','')
    print(f'Trying: {host} with user {user}')
    try:
        conn = psycopg2.connect(url)
        print('SUCCESS! URL works.')
        conn.close()
        break
    except Exception as e:
        print(f'FAILED: {e}')
