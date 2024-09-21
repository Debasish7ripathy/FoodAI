from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from PIL import Image
import os, json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'f68d0703edd511a7fba30a685a93af31'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

# Configure Google AI
genai.configure(api_key='AIzaSyCD1hb6mif1WnG5ViXg80ZFmXN19saZ1CM')
safety_settings = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}
model = genai.GenerativeModel("gemini-1.5-flash", safety_settings=safety_settings)

# Database Models
class User(db.Model):
    uid = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    medical_condition = db.Column(db.String(200))
    diet = db.Column(db.String(200))
    profession = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    credits = db.Column(db.Integer, default=100)

class PantryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('user.uid'), nullable=False)
    sno = db.Column(db.Integer, nullable=False)
    food_item = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float)
    energy_value = db.Column(db.Float)
    protein = db.Column(db.Float)
    carbs = db.Column(db.Float)
    fat = db.Column(db.Float)
    last_order_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    health_rate = db.Column(db.Float)

class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('user.uid'), nullable=False)
    sno = db.Column(db.Integer, nullable=False)
    food_name = db.Column(db.String(100), nullable=False)
    ingredient_list = db.Column(db.String(500))
    energy_value = db.Column(db.Float)
    protein = db.Column(db.Float)
    fat = db.Column(db.Float)
    remaining_calories = db.Column(db.Float)

# Routes
@app.route('/')
def home():
    if 'uid' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['uid'] = user.uid
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_password = generate_password_hash(request.form['password'])
        new_user = User(username=request.form['username'], 
                        password=hashed_password,
                        email=request.form['email'],
                        age=request.form['age'],
                        gender=request.form['gender'],
                        medical_condition=request.form['medical_condition'],
                        diet=request.form['diet'],
                        profession=request.form['profession'])
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'uid' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['uid'])
    return render_template('dashboard.html', user=user)

@app.route('/pantry')
def pantry():
    if 'uid' not in session:
        return redirect(url_for('login'))
    items = PantryItem.query.filter_by(uid=session['uid']).all()
    return render_template('pantry.html', items=items)

@app.route('/add_pantry_item', methods=['POST'])
def add_pantry_item():
    if 'uid' not in session:
        return redirect(url_for('login'))
    # Implement item addition logic here
    return redirect(url_for('pantry'))

@app.route('/daily_menu')
def daily_menu():
    if 'uid' not in session:
        return redirect(url_for('login'))
    menu_items = MenuItem.query.filter_by(uid=session['uid']).all()
    return render_template('daily_menu.html', menu_items=menu_items)

@app.route('/lens_analysis', methods=['GET', 'POST'])
def lens_analysis():
    if 'uid' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Implement image analysis logic here using Google AI model
        file = request.files['file']
        if file:
            image_path = os.path.join('uploads', file.filename)
            file.save(image_path)
            user = User.query.get(session['uid'])
            health_data = f"Age: {user.age}, Gender: {user.gender}, Medical Condition: {user.medical_condition}, Diet: {user.diet}"
            analysis_result = classify_image(image_path, health_data)
            return jsonify(analysis_result)
    return render_template('lens_analysis.html')

@app.route('/health_assistant')
def health_assistant():
    if 'uid' not in session:
        return redirect(url_for('login'))
    # Implement health assistant logic here
    return render_template('health_assistant.html')

def classify_image(image_path, health_data):
    try:
        image = Image.open(image_path)
        prompt = [
            f"Analyze the image and provide the following information in JSON format:",
            "1. List of ingredients and their approximate quantities",
            "2. Whether it's healthy or not",
            "3. Estimated calories and nutrients",
            f"4. Health score out of 100 based on the following health parameters: {health_data}",
            "5. Deliciousness score out of 100",
            "6. Give the name of the food item",
            "7. Suggest if I should eat it or not and if so, make it such a way that it should be healthy and nutritious"
        ]
        response = model.generate_content([image] + prompt, safety_settings=safety_settings)
       
        if response.candidates[0].content is None:
            safety_ratings = response.candidates[0].safety_ratings
            return {"error": f"Response blocked due to safety concerns: {safety_ratings}"}
       
        return json.loads(response.text)
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)