# Put it online for free (Render + Aiven MySQL)

1. Aiven (aiven.io): create a free MySQL service. Note Host, Port, User, Password, Database name; download the CA certificate and save it as `ca.pem` in this folder.
2. On your laptop, in this folder (Windows cmd):
   set DB_HOST=...  set DB_PORT=...  set DB_USER=avnadmin  set DB_PASSWORD=...  set DB_NAME=defaultdb  set DB_SSL_CA=ca.pem
   set OWNER_PASSWORD=choose-one  set STAFF_PASSWORD=choose-another
   python -m pip install -r requirements.txt
   python init_db.py
3. Upload this folder's files (including ca.pem) to a new GitHub repository.
4. Render (render.com): New > Web Service > pick the repo. Build: `pip install -r requirements.txt`. Start: `gunicorn app:app`. Instance type: Free.
   Environment variables: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_SSL_CA=ca.pem, SECRET_KEY=(long random text).
5. Open the .onrender.com link. Free services sleep after 15 minutes idle and take about a minute to wake, so open it before presenting.
