# SGW Landing Page Deployment

This package contains everything needed to deploy the SGW (Smart Goal Wallet) landing page to `cosseboomlab.com/sgw`.

## Files Included

- `sgw_landing_page.html` - The SGW landing page
- `pesticide-search-key-new.pem` - SSH key for EC2 instance
- `deploy_instructions.md` - Step-by-step deployment instructions

## Quick Deployment

1. **SSH into your EC2 instance:**
   ```bash
   ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224
   ```

2. **Create the application directory:**
   ```bash
   mkdir -p /home/ubuntu/pesticide-search
   cd /home/ubuntu/pesticide-search
   ```

3. **Upload the SGW page:**
   ```bash
   # From your local machine:
   scp -i pesticide-search-key-new.pem sgw_landing_page.html ubuntu@3.144.200.224:/home/ubuntu/pesticide-search/
   ```

4. **Set up the Flask application:**
   ```bash
   # On the EC2 instance:
   mkdir -p templates
   mv sgw_landing_page.html templates/sgw.html
   
   # Create Flask app if it doesn't exist
   cat > pesticide_search.py << 'EOF'
   from flask import Flask, render_template
   
   app = Flask(__name__)
   
   @app.route("/")
   def home():
       return render_template("index.html")
   
   @app.route("/sgw")
   def sgw():
       return render_template("sgw.html")
   
   if __name__ == "__main__":
       app.run(host="0.0.0.0", port=5000, debug=True)
   EOF
   
   # Create requirements.txt
   echo "Flask==2.3.3" > requirements.txt
   
   # Set up virtual environment
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Start the application
   nohup python pesticide_search.py > app.log 2>&1 &
   ```

5. **Verify deployment:**
   ```bash
   # Check if app is running
   ps aux | grep python
   
   # View logs
   tail -f app.log
   ```

## Alternative: Use AWS Systems Manager Session Manager

If SSH is not working, you can use AWS Systems Manager Session Manager:

1. Go to AWS Console → EC2 → Instances
2. Select your instance (i-0f842f7f154dfda2d)
3. Click "Connect" → "Session Manager"
4. Click "Connect"
5. Follow the deployment steps above in the Session Manager terminal

## Troubleshooting

- **Connection timeout:** Check if the instance is running and security group allows SSH
- **Permission denied:** Make sure the SSH key has correct permissions (chmod 400)
- **App not starting:** Check the logs in app.log for error messages

## Expected Result

After successful deployment, the SGW landing page should be available at:
`http://cosseboomlab.com/sgw`

The page includes:
- Modern, responsive design
- Feature showcase for Smart Goal Wallet
- Technology stack information
- Download buttons (coming soon)
- Professional styling with animations 