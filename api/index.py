from flask import Flask, jsonify
import os
import requests

app = Flask(__name__)

@app.route('/api/links', methods=['GET'])
def get_links():
    # Ngambil kredensial dari Environment Variables Vercel
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        return jsonify({"error": "Database credentials missing"}), 500

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}"
    }
    
    # Hit API Supabase buat narik semua isi tabel 'links'
    # Pastikan di Vercel SUPABASE_URL isinya cuma base URL (contoh: https://xyz.supabase.co)
    endpoint = f"{supabase_url}/rest/v1/links?select=*"
    
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Vercel butuh variable 'app' di global scope
if __name__ == '__main__':
    app.run(debug=True)
