from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
import os
from sqlalchemy.exc import OperationalError
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
db = SQLAlchemy()

def get_database_url():
    db_user = os.environ.get('DB_USER', 'postgres')
    db_password = os.environ.get('DB_PASSWORD', 'password')
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_name = os.environ.get('DB_NAME', 'testdb')
    
    # Try to connect to PostgreSQL
    postgres_url = f'postgresql://{db_user}:{db_password}@{db_host}/{db_name}'
    try:
        engine = db.create_engine(postgres_url)
        engine.connect()
        logging.info("Connected to PostgreSQL")
        return postgres_url
    except OperationalError as e:
        logging.error(f"PostgreSQL connection failed: {e}")
        logging.error("Database connection error - falling back to SQLite")
        return 'sqlite:///local_cache.db'

# Configure the SQLAlchemy database connection
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()

# Initialize the app with the extension
db.init_app(app)

# Define a simple model
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)

    def __repr__(self):
        return f'<Item {self.name}>'

# HTML template
HTML = '''
<!doctype html>
<html>
    <head>
        <title>Item Manager</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            h1 { color: #333; }
            form { margin-bottom: 20px; }
            ul { list-style-type: none; padding: 0; }
            li { margin-bottom: 10px; }
            .status { color: #666; font-style: italic; }
        </style>
    </head>
    <body>
        <h1>Item Manager</h1>
        <p class="status">Database: {{ db_type }}</p>
        <form method="POST">
            <input type="text" name="name" placeholder="Enter item name" required>
            <input type="submit" value="Add Item">
        </form>
        <h2>Items:</h2>
        <ul>
            {% for item in items %}
                <li>{{ item.name }}</li>
            {% endfor %}
        </ul>
    </body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            name = request.form['name']
            if not name or len(name.strip()) == 0:
                logging.error("Empty item name provided")
                raise ValueError("Item name cannot be empty")
            new_item = Item(name=name)
            db.session.add(new_item)
            db.session.commit()
            logging.info(f"Added new item: {name}")
        items = Item.query.all()
        db_type = "PostgreSQL" if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI'] else "SQLite (Local Cache)"
        return render_template_string(HTML, items=items, db_type=db_type)
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        db.session.rollback()
        return f"An error occurred: {str(e)}", 500

@app.route('/items', methods=['GET'])
def get_items():
    try:
        items = Item.query.all()
        logging.info(f"Retrieved {len(items)} items")
        return jsonify([{"id": item.id, "name": item.name} for item in items])
    except Exception as e:
        logging.error(f"Error retrieving items: {str(e)}")
        return jsonify({"error": "Failed to retrieve items"}), 500

@app.route('/error-test')
def error_test():
    """Route to generate test errors"""
    logging.error("Test error log generated")
    logging.warning("Test warning log generated")
    logging.critical("Test critical log generated")
    return "Error logs generated", 200

# Create tables
with app.app_context():
    db.create_all()

#if __name__ == '__main__':
    # Add a delay to allow time for the database to be ready
#    time.sleep(10)
#    app.run(host='0.0.0.0', port=80)
