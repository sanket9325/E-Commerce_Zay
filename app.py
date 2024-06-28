from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename

import MySQLdb.cursors
from urllib.parse import urlencode
import json
import os
import random
import string
from datetime import datetime

app = Flask(__name__)
mysql = MySQL(app)

app.secret_key = os.urandom(24).hex()
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'ecom_project'

app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


def getUserDataById(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        return user_data


app.jinja_env.globals.update(getUserDataById=getUserDataById)


@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    msg = ''
    if session.get('admin_loggedin'):
        return redirect(url_for('admin_dashboard'))
    else:
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']
            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cur.execute("SELECT * FROM admin WHERE email = %s AND password = %s", (email, password))
            data = cur.fetchone()
            if data:
                session['admin-email'] = email
                session['admin_loggedin'] = True
                return redirect(url_for('admin_dashboard'))
            else:
                msg = 'Please enter the correct details.'
                return render_template('admin/index.html', msg=msg)
        return render_template('admin/index.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_loggedin', None)
    session.pop('admin_email', None)
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user_transactions ORDER BY id DESC LIMIT 10")
        recent_transactions = cursor.fetchall()
        return render_template('admin/dashboard.html', recent_transactions=recent_transactions)
    else:
        return redirect(url_for('admin_login'))


@app.route('/admin/categories', methods=['GET', 'POST'])
def admin_categories():
    if session.get('admin_loggedin'):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM product_categories")
        categories = cur.fetchall()
        return render_template('admin/categories.html', categories=categories)
    else:
        return redirect(url_for('admin_login'))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/admin/addCategory', methods=['GET', 'POST'])
def admin_add_category():
    if session.get('admin_loggedin'):
        if request.method == 'POST':
            # Retrieve form data
            category_name = request.form['category_name']
            category_desc = request.form['category_desc']
            category_file = request.files['category_file']

            # Validate and store the image file
            if category_file and allowed_file(category_file.filename):
                filename = secure_filename(category_file.filename)
                category_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            else:
                # Handle invalid file format
                return render_template('admin/add-category.html', msg='Invalid file format')

            # Insert into the database
            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cur.execute("INSERT INTO product_categories (name, thumbnail, description) VALUES (%s, %s, %s)",
                        (category_name, filename, category_desc))
            mysql.connection.commit()
            return render_template('admin/add-category.html', msg="Category added!")
        return render_template('admin/add-category.html')
    else:
        return redirect(url_for('admin_login'))


@app.route('/admin/editCategory/<int:category_id>', methods=['GET', 'POST'])
def admin_edit_category(category_id):
    if session.get('admin_loggedin'):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM product_categories WHERE id = %s", (category_id,))
        category_data = cur.fetchone()
        print(category_data)
        return render_template('admin/edit-category.html', category_data=category_data)
    else:
        return redirect(url_for('admin_login'))


@app.route('/admin/updateCategory', methods=['GET', 'POST'])
def admin_update_category():
    if session.get('admin_loggedin'):
        if request.method == 'POST':
            category_name = request.form['category_name']
            category_desc = request.form['category_desc']
            category_id = request.form['category_id']
            category_file = request.files['category_file']

            # Get the existing category data from the database
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM product_categories WHERE id = %s", (category_id,))
            category_data = cursor.fetchone()

            if category_data:
                # Update the category name and description
                cursor.execute("UPDATE product_categories SET name = %s, description = %s WHERE id = %s",
                               (category_name, category_desc, category_id))
                mysql.connection.commit()

                # Update the category image if a new file is uploaded
                if category_file and allowed_file(category_file.filename):
                    # Delete the existing image file
                    if category_data['thumbnail']:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], category_data['thumbnail']))

                    # Save the new image file
                    filename = secure_filename(category_file.filename)
                    category_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    # Update the category image in the database
                    cursor.execute("UPDATE product_categories SET thumbnail = %s WHERE id = %s",
                                   (filename, category_id))
                    mysql.connection.commit()

            return redirect(url_for('admin_categories'))

        return redirect(url_for('admin_categories'))

    return redirect(url_for('admin_login'))


@app.route('/admin/deleteCategory/<int:category_id>', methods=['GET', 'POST'])
def admin_delete_category(category_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Check if the category exists in the database
        cursor.execute("SELECT * FROM product_categories WHERE id = %s", (category_id,))
        category_data = cursor.fetchone()
        if category_data:
            # Delete the category image file from the uploads folder
            if category_data['thumbnail']:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], category_data['thumbnail']))

            # Delete the category from the database
            cursor.execute("DELETE FROM product_categories WHERE id = %s", (category_id,))
            mysql.connection.commit()
            # DELETE products related to that category
            cursor.execute("DELETE FROM products WHERE category_id = %s", (category_id,))
            mysql.connection.commit()

        return redirect(url_for('admin_categories'))

    return redirect(url_for('admin_login'))


def getAllCategories():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM product_categories")
    categories = cur.fetchall()
    if categories:
        return categories


app.jinja_env.globals.update(getAllCategories=getAllCategories)


def getCategoryDataById(category_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM product_categories WHERE id = %s", (category_id))
    category_data = cur.fetchone()
    if category_data:
        return category_data


app.jinja_env.globals.update(getCategoryDataById=getCategoryDataById)


def getCategoryNameById(category_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM product_categories WHERE id = %s", (category_id,))
    category_data = cur.fetchone()
    return category_data['name']


app.jinja_env.globals.update(getCategoryNameById=getCategoryNameById)


@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    if session.get('admin_loggedin'):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM products")
        products = cur.fetchall()
        return render_template('admin/products.html', products=products)
    else:
        return redirect(url_for('admin_login'))


@app.route('/admin/addProduct', methods=['GET', 'POST'])
def admin_add_product():
    if session.get('admin_loggedin'):
        categories = getAllCategories()
        if request.method == 'POST':
            # Retrieve form data
            product_name = request.form['product_name']
            product_desc = request.form['product_desc']
            product_file = request.files['product_file']
            product_category = request.form['product_category']
            product_price = request.form['product_price']
            product_total = request.form['product_total']

            # Validate and store the image file
            if product_file and allowed_file(product_file.filename):
                filename = secure_filename(product_file.filename)
                product_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            else:
                # Handle invalid file format
                return render_template('admin/add-product.html', msg='Invalid file format')

            # Insert into the database
            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cur.execute(
                "INSERT INTO products (name, category_id, description, price, thumbnail,total) VALUES (%s, %s, %s, %s, %s,%s)",
                (product_name, product_category, product_desc, product_price, filename, product_total))
            mysql.connection.commit()
            return render_template('admin/add-product.html', msg="Product added!", categories=categories)
        return render_template('admin/add-product.html', categories=categories)
    else:
        return redirect(url_for('admin_login'))


@app.route('/admin/editProduct/<int:product_id>', methods=['GET', 'POST'])
def admin_edit_product(product_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product_data = cursor.fetchone()
        categories = getAllCategories()

        if not product_data:

            return redirect(url_for('admin_dashboard'))

        if request.method == 'POST':
            # Handle form submission for editing product details
            # Assuming form fields are named similar to database columns
            # You need to add the logic here to update the product details in the database
            pass  # Add your code here for updating the product details

        # Fetch related products
        cursor.execute("SELECT * FROM products WHERE category_id = %s AND id != %s ORDER BY RAND() LIMIT 4",
                       (product_data['category_id'], product_id))
        related_products = cursor.fetchall()

        # Fetching product IDs and their total quantities
        cursor.execute("SELECT id, total FROM products")
        product_quantities = {row['id']: row['total'] for row in cursor.fetchall()}

        print_data = []  # List to store print statement data

        # Fetching orders and calculating the total number of orders for each product
        for product_id, total_quantity in product_quantities.items():
            cursor.execute("SELECT COUNT(*) AS order_count FROM orders WHERE product_id = %s", (product_id,))
            order_count = cursor.fetchone()['order_count']

            cursor.execute("SELECT SUM(quantity) AS sold_quantity FROM user_transactions WHERE product_id = %s",
                           (product_id,))
            sold_quantity = cursor.fetchone()['sold_quantity'] or 0

            print_data.append({
                "product_id": product_id,
                "total_quantity": total_quantity,
                "sold_quantity": sold_quantity,
                "order_count": order_count,
                "available": total_quantity - sold_quantity
            })

            # Update the availability status in the products table
            available_quantity = total_quantity - sold_quantity
            cursor.execute("UPDATE products SET avalible=%s, sold=%s WHERE id=%s",
                           (available_quantity, sold_quantity, product_id))

        total_available = sum(product_quantities.values())

        return render_template('admin/edit-product.html', product_data=product_data, categories=categories,
                               related_products=related_products, total_available=total_available,
                               print_data=print_data)
    else:
        return redirect(url_for('admin_login'))



@app.route('/admin/updateProduct', methods=['GET', 'POST'])
def admin_update_product():
    if session.get('admin_loggedin'):
        if request.method == 'POST':
            product_name = request.form['product_name']
            product_desc = request.form['product_desc']
            product_category = request.form['product_category']
            product_file = request.files['product_file']
            product_id = request.form['product_id']
            product_price = request.form['product_price']
            product_total = request.form['product_total']

            # Get the existing category data from the database
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            product_data = cursor.fetchone()

            if product_data:
                # Update the category name and description
                cursor.execute(
                    "UPDATE products SET name = %s, description = %s, price = %s, category_id = %s, total = %s WHERE id = %s",
                    (product_name, product_desc, product_price, product_category, product_total,product_id))
                mysql.connection.commit()

                # Update the category image if a new file is uploaded
                if product_file and allowed_file(product_file.filename):
                    # Delete the existing image file
                    if product_data['thumbnail']:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], product_data['thumbnail']))

                    # Save the new image file
                    filename = secure_filename(product_file.filename)
                    product_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    # Update the category image in the database
                    cursor.execute("UPDATE products SET thumbnail = %s WHERE id = %s",
                                   (filename, product_id))
                    mysql.connection.commit()

            return redirect(url_for('admin_products'))

        return redirect(url_for('admin_products'))

    return redirect(url_for('admin_login'))


@app.route('/admin/deleteProduct/<int:product_id>', methods=['GET', 'POST'])
def admin_delete_Product(product_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Check if the category exists in the database
        cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product_data = cursor.fetchone()
        if product_data:
            # Delete the category image file from the uploads folder
            if product_data['thumbnail']:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], product_data['thumbnail']))

            # Delete the category from the database
            cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
            mysql.connection.commit()

        return redirect(url_for('admin_products'))

    return redirect(url_for('admin_login'))


@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        users_count = cursor.rowcount
        return render_template('admin/users.html', users=users, users_count=users_count)
    return redirect(url_for('admin_login'))


@app.route('/admin/addUser', methods=['GET', 'POST'])
def admin_add_user():
    if session.get('admin_loggedin'):
        if request.method == 'POST':
            name = request.form['user_name']
            email = request.form['user_email']
            password = request.form['user_password']
            mobile = request.form['user_mobile']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM users WHERE email = %s AND mobile = %s", (email, mobile))
            data = cursor.fetchone()
            if data:
                return render_template('admin/add-user.html',
                                       msg='Email or mobile already exists. Please try another one.')
            else:
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("INSERT INTO users (name, email, password, mobile) VALUES (%s, %s, %s, %s)",
                               (name, email, password, mobile))
                mysql.connection.commit()
                return redirect(url_for('admin_users'))
        return render_template('admin/add-user.html')
    return redirect(url_for('admin_login'))


@app.route('/admin/editUser/<int:user_id>', methods=['GET', 'POST'])
def admin_edit_user(user_id):
    if session.get('admin_loggedin'):
        if request.method == 'POST':
            name = request.form['user_name']
            email = request.form['user_email']
            password = request.form['user_password']
            mobile = request.form['user_mobile']
            user_id = request.form['user_id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM users WHERE (email = %s OR mobile = %s) AND id != %s",
                           (email, mobile, user_id))
            data = cursor.fetchone()
            if data:
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                return render_template("admin/edit-user.html", user=user,
                                       msg="Email or mobile already exists. Please try other one.")
            else:
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("UPDATE users SET name = %s, email = %s, mobile = %s, password = %s WHERE id = %s",
                               (name, email, mobile, password, user_id))
                mysql.connection.commit()
                return redirect(url_for('admin_users'))
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        return render_template('admin/edit-user.html', user=user)
    return redirect(url_for('admin_login'))


@app.route('/admin/deleteUser/<int:user_id>', methods=['GET', 'POST'])
def admin_delete_user(user_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE users SET status = 2 WHERE id = %s", (user_id,))
        mysql.connection.commit()
        return redirect(url_for('admin_users'))
    return redirect(url_for('admin_login'))


@app.route('/admin/activeUser/<int:user_id>', methods=['GET', 'POST'])
def admin_active_user(user_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE users SET status = 1 WHERE id = %s", (user_id,))
        mysql.connection.commit()
        return redirect(url_for('admin_users'))
    return redirect(url_for('admin_login'))


@app.route('/admin/transactions', methods=['GET', 'POST'])
def admin_transactions():
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user_transactions")
        transactions = cursor.fetchall()
        transactions_count = cursor.rowcount
        return render_template('admin/transactions.html', transactions=transactions,
                               transactions_count=transactions_count)
    return redirect(url_for('admin_login'))


@app.route('/admin/orders', methods=['GET', 'POST'])
def admin_orders():
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM orders")
        orders = cursor.fetchall()
        orders_count = cursor.rowcount
        return render_template('admin/orders.html', orders=orders, orders_count=orders_count)
    return redirect(url_for('admin_login'))


@app.route('/admin/conOrder/<int:order_id>', methods=['GET', 'POST'])
def admin_con_order(order_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE orders SET status = %s WHERE id = %s", ('confirmed', order_id))
        mysql.connection.commit()
        return redirect(url_for('admin_orders'))
    return redirect(url_for('admin_login'))


@app.route('/admin/penOrder/<int:order_id>', methods=['GET', 'POST'])
def admin_pen_order(order_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE orders SET status = %s WHERE id = %s", ('pending', order_id))
        mysql.connection.commit()
        return redirect(url_for('admin_orders'))
    return redirect(url_for('admin_login'))


@app.route('/admin/proOrder/<int:order_id>', methods=['GET', 'POST'])
def admin_pro_order(order_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE orders SET status = %s WHERE id = %s", ('processing', order_id))
        mysql.connection.commit()
        return redirect(url_for('admin_orders'))
    return redirect(url_for('admin_login'))


@app.route('/admin/comOrder/<int:order_id>', methods=['GET', 'POST'])
def admin_com_order(order_id):
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE orders SET status = %s WHERE id = %s", ('complete', order_id))
        mysql.connection.commit()
        return redirect(url_for('admin_orders'))
    return redirect(url_for('admin_login'))


@app.route('/admin/ratings', methods=['GET', 'POST'])
def admin_ratings():
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM product_ratings")
        ratings = cursor.fetchall()
        ratings_count = cursor.rowcount
        return render_template('admin/ratings.html', ratings=ratings, ratings_count=ratings_count)
    return redirect(url_for('admin_login'))


@app.route('/admin/reviews', methods=['GET', 'POST'])
def admin_reviews():
    if session.get('admin_loggedin'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM product_reviews")
        reviews = cursor.fetchall()
        reviews_count = cursor.rowcount
        return render_template('admin/reviews.html', reviews=reviews, reviews_count=reviews_count)
    return redirect(url_for('admin_login'))


################################################# FRONT END #####################################################

def getFeatureProducts():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM products ORDER BY RAND() LIMIT 3")
    products = cur.fetchall()
    return products


app.jinja_env.globals.update(getFeatureProducts=getFeatureProducts)


@app.route('/inactive')
def inactive_user():
    return render_template('inactive.html')


@app.route('/status', methods=['GET', 'POST'])
def checkUserStatus():
    if 'user_loggedin' in session and session['user_loggedin']:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cur.fetchone()
        if user['status'] == 2:
            return '2'


@app.route('/search', methods=['GET', 'POST'])
def searchp():
    if request.method == 'POST':
        search = request.form['search']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Construct the SQL query to search in both 'name' and 'description' columns
        sql_query = "SELECT * FROM products WHERE name LIKE %s OR description LIKE %s"
        keyword = f"%{search}%"  # Add wildcard '%' to search for partial matches
        cursor.execute(sql_query, (keyword, keyword))
        products = cursor.fetchall()
        return render_template('search.html', products=products)


@app.route('/about', methods=['GET', 'POST'])
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    return render_template('contact.html')


@app.route('/', methods=['GET', 'POST'])
def index():
    categories = getAllCategories()
    feature_products = getFeatureProducts()
    msg = request.args.get('msg')
    if msg:
        return render_template('index.html', categories=categories, feature_products=feature_products, msg=msg)
    return render_template('index.html', categories=categories, feature_products=feature_products)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        data = cur.fetchone()
        if data:
            session['user_email'] = email
            session['user_id'] = data['id']
            session['user_loggedin'] = True
            return redirect(url_for('index'))
        else:
            msg = 'Please enter the correct details.'
            return render_template('login.html', msg=msg)
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_name = request.form['name']
        user_email = request.form['email']
        user_mobile = request.form['mobile']
        user_password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s AND mobile = %s", (user_email, user_mobile))
        user_data = cursor.fetchone()
        if user_data:
            return render_template('register.html', msg='Account exists on entered email or mobile.')
        else:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("INSERT INTO users(name, email, password, mobile) VALUES(%s, %s, %s, %s)",
                           (user_name, user_email, user_password, user_mobile))
            mysql.connection.commit()
            return render_template('register.html', msg='Your account has been created. Please login.')
    return render_template('register.html')


@app.route('/category/<int:category_id>', methods=['GET', 'POST'])
def single_category_shop(category_id):
    param_products = request.args.get('products')
    param_category_name = request.args.get('category_name')
    param_category_id = request.args.get('category_id')
    if param_products and param_category_name and param_category_id:
        products = eval(param_products)  # Convert string back to list
        return json.dumps(
            {'products': products, 'category_name': param_category_name, 'category_id': param_category_id})
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM products WHERE category_id = %s", (category_id,))
    products = cursor.fetchall()
    products_count = cursor.rowcount
    if products_count:
        category_name = getCategoryNameById(category_id)
        return render_template('category-shop.html', products=products, category_name=category_name,
                               category_id=category_id, products_count=products_count)
    else:
        category_name = getCategoryNameById(category_id)
        return render_template('category-shop.html', products=products, category_name=category_name,
                               category_id=category_id, products_count=products_count)


@app.route('/addFavorite', methods=['GET', 'POST'])
def addFavorite():
    if request.method == 'POST':
        if 'user_loggedin' in session and session['user_loggedin']:
            product_id = request.form['product_id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM user_favorites WHERE user_id = %s AND product_id = %s",
                           (session['user_id'], product_id))
            favorite_data = cursor.fetchone()
            if favorite_data:
                return 'Product is already added in Favorites.'
            else:
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("INSERT INTO user_favorites(user_id, product_id) VALUES(%s, %s)",
                               (session['user_id'], product_id))
                mysql.connection.commit()
                return 'Product has been added to Favorites.'
        else:
            return 'Please log in to add the product to your favorites.'


@app.route('/addToCart', methods=['GET', 'POST'])
def addToCart():
    if request.method == 'POST':
        if 'user_loggedin' in session and session['user_loggedin']:
            product_id = request.form['product_id']
            quantity = request.form['quantity']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM user_cart WHERE user_id = %s AND product_id = %s",
                           (session['user_id'], product_id))
            cart_data = cursor.fetchone()
            if cart_data:
                return 'Product is already added in cart.'
            else:
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("INSERT INTO user_cart(user_id, product_id, quantity) VALUES(%s, %s, %s)",
                               (session['user_id'], product_id, quantity))
                mysql.connection.commit()
                return 'Product has been added to Cart.'
        else:
            return 'Please login to add product in your cart.'


def userCartItems():
    if 'user_loggedin' in session and session['user_loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user_cart WHERE user_id = %s", (session['user_id'],))
        total_items = cursor.fetchall()
        total_items_count = 0
        for item in total_items:
            total_items_count += int(item['quantity'])
        return total_items_count


app.jinja_env.globals.update(userCartItems=userCartItems)


@app.route('/filterProducts', methods=['POST'])
def filterProducts():
    if request.method == 'POST':
        filter_value = int(request.form['filter_value'])
        category_id = int(request.form['category_id'])
        if filter_value == 1:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM products WHERE category_id = %s ORDER BY RAND() LIMIT 1", (category_id,))
            products = cursor.fetchall()
            category_name = getCategoryNameById(category_id)
            query_params = urlencode({'products': products, 'category_name': category_name, 'category_id': category_id})
            redirect_url = f"/category/{category_id}?{query_params}"
            return redirect(redirect_url)
        if filter_value == 2:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM products WHERE category_id = %s", (category_id,))
            products = cursor.fetchall()
            category_name = getCategoryNameById(category_id)
            query_params = urlencode({'products': products, 'category_name': category_name, 'category_id': category_id})
            redirect_url = f"/category/{category_id}?{query_params}"
            return redirect(redirect_url)
        if filter_value == 3:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM products WHERE category_id = %s", (category_id,))
            products = cursor.fetchall()
            category_name = getCategoryNameById(category_id)
            query_params = urlencode({'products': products, 'category_name': category_name, 'category_id': category_id})
            redirect_url = f"/category/{category_id}?{query_params}"
            return redirect(redirect_url)


@app.route('/userCartAddedItems', methods=['GET', 'POST'])
def userCartAddedItems():
    if 'user_loggedin' in session and session['user_loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user_cart WHERE user_id = %s", (session['user_id'],))
        total_rows = cursor.rowcount
        return jsonify(total_rows=total_rows)
    return jsonify(total_rows=0)

@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def product(product_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product_data = cursor.fetchone()

    if not product_data:
        return redirect(url_for('homepage'))

    category_id = product_data['category_id']
    cursor.execute("SELECT * FROM products WHERE category_id = %s AND id != %s ORDER BY RAND() LIMIT 4",
                   (category_id, product_id))
    related_products = cursor.fetchall()

    if 'user_loggedin' in session and session['user_loggedin']:
        cursor.execute("SELECT * FROM user_cart WHERE user_id = %s", (session['user_id'],))
        items = cursor.fetchall()

        # Fetching product IDs and their total quantities
        cursor.execute("SELECT id, total FROM products")
        product_quantities = {row['id']: row['total'] for row in cursor.fetchall()}

        print_data = []  # List to store print statement data

        # Fetching orders and calculating the total number of orders for each product
        for product_id, total_quantity in product_quantities.items():
            cursor.execute("SELECT COUNT(*) AS order_count FROM orders WHERE product_id = %s", (product_id,))
            order_count = cursor.fetchone()['order_count']

            cursor.execute("SELECT SUM(quantity) AS sold_quantity FROM user_transactions WHERE product_id = %s",
                           (product_id,))
            sold_quantity = cursor.fetchone()['sold_quantity'] or 0

            print_data.append({
                "product_id": product_id,
                "total_quantity": total_quantity,
                "sold_quantity": sold_quantity,
                "order_count": order_count,
                "available": total_quantity - sold_quantity
            })

            # Update the availability status in the products table
            available_quantity = total_quantity - sold_quantity
            cursor.execute("UPDATE products SET avalible=%s, sold=%s WHERE id=%s",
                           (available_quantity, sold_quantity, product_id))

        total_available = sum(product_quantities.values())
        return render_template('single-product.html', product_data=product_data, related_products=related_products,
                               total_available=total_available, product_quantities=product_quantities,
                               print_data=print_data, items=items)
    else:
        return redirect(url_for('login'))


# @app.route('/product/<int:product_id>', methods=['GET', 'POST'])
# def product(product_id):
#     cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
#     cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
#     product_data = cursor.fetchone()
#
#     if not product_data:
#
#         return redirect(url_for('homepage'))
#
#     category_id = product_data['category_id']
#     cursor.execute("SELECT * FROM products WHERE category_id = %s AND id != %s ORDER BY RAND() LIMIT 4",
#                    (category_id, product_id))
#     related_products = cursor.fetchall()
#
#     if 'user_loggedin' in session and session['user_loggedin']:
#         cursor.execute("SELECT * FROM user_cart WHERE user_id = %s", (session['user_id'],))
#         items = cursor.fetchall()
#
#         # Fetching product IDs and their total quantities
#         cursor.execute("SELECT id, total FROM products")
#         product_data = cursor.fetchall()
#
#         print_data = []  # List to store print statement data
#
#         product_quantities = {}  # Dictionary to store product ID and total quantity
#         for row in product_data:
#             product_id = row['id']
#             total_quantity = row['total']
#             product_quantities[product_id] = total_quantity
#
#         # Fetching orders and calculating the total number of orders for each product
#         product_orders = {}  # Dictionary to store product ID and order count
#         for product_id, total_quantity in product_quantities.items():
#             cursor.execute("SELECT COUNT(*) AS order_count FROM orders WHERE product_id = %s", (product_id,))
#             order_count_data = cursor.fetchone()
#             order_count = order_count_data['order_count']
#             product_orders[product_id] = order_count
#
#             cursor.execute("SELECT SUM(quantity) AS sold_quantity FROM user_transactions WHERE product_id = %s",
#                            (product_id,))
#             sold_quantity_data = cursor.fetchone()
#             sold_quantity = sold_quantity_data['sold_quantity']
#             if sold_quantity is None:
#                 sold_quantity = 0  # If no transactions found, set sold quantity to 0
#
#             print(
#                 f"Product ID: {product_id}, Total Product: {total_quantity}, Sold Product: {sold_quantity}, Orders: {order_count}, Available: {total_quantity - sold_quantity}")
#             print_data.append({
#                 "product_id": product_id,
#                 "total_quantity": total_quantity,
#                 "sold_quantity": sold_quantity,
#                 "order_count": order_count,
#                 "available": total_quantity - sold_quantity
#             })
#
#             # Update the availability status in the products table
#             available_quantity = total_quantity - sold_quantity
#
#             cursor.execute("UPDATE products SET avalible=%s, sold=%s WHERE id=%s",
#                            (available_quantity, sold_quantity, product_id))
#
#         total_available = sum(product_quantities.values())
#         return render_template('single-product.html', product_data=product_data, related_products=related_products,
#                                total_available=available_quantity, product_quantities=product_quantities,
#                                print_data=print_data, items=items)
#     else:
#         return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_loggedin' in session and session['user_loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user_data = cursor.fetchone()
        if user_data:
            if request.method == 'POST':
                user_name = request.form['user_name']
                user_email = request.form['user_email']
                user_password = request.form['user_password']
                user_mobile = request.form['user_mobile']
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("SELECT * FROM users WHERE (email = %s OR mobile = %s) AND id != %s",
                               (user_email, user_mobile, session['user_id']))
                data = cursor.fetchone()
                if data:
                    return render_template('profile.html', user_data=user_data,
                                           msg='The entered details already exist. Please try another email or mobile.')
                else:
                    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                    cursor.execute("UPDATE users SET name = %s, email = %s, password = %s, mobile = %s WHERE id = %s",
                                   (user_name, user_email, user_password, user_mobile, session['user_id']))
                    mysql.connection.commit()
                    return render_template('profile.html', user_data=user_data,
                                           msg='Details have been updated. Please refresh the window.')
            else:
                return render_template('profile.html', user_data=user_data)
    else:
        return redirect(url_for('login'))


@app.route('/favorites', methods=['GET', 'POST'])
def favorites():
    if 'user_loggedin' in session and session['user_loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * from user_favorites WHERE user_id = %s", (session['user_id'],))
        favorites = cursor.fetchall()
        return render_template('favorites.html', favorites=favorites)
    else:
        return redirect(url_for('login'))


def getProductDataById(product_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product_data = cur.fetchone()
    return product_data


app.jinja_env.globals.update(getProductDataById=getProductDataById)


@app.route('/removeFavorite', methods=['GET', 'POST'])
def removeFavorite():
    if 'user_loggedin' in session and session['user_loggedin']:
        if request.method == 'POST':
            product_id = request.form['product_id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("DELETE FROM user_favorites WHERE user_id = %s AND product_id = %s",
                           (session['user_id'], product_id))
            mysql.connection.commit()
            return '1'


@app.route('/addRating', methods=['GET', 'POST'])
def add_rating():
    if 'user_loggedin' in session and session['user_loggedin']:
        if request.method == 'POST':
            product_id = request.form['product_id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * from product_ratings WHERE product_id = %s and user_id = %s",
                           (product_id, session['user_id']))
            data = cursor.fetchone()
            if data:
                return '3'  # already done
            else:
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("SELECT * FROM orders WHERE product_id = %s AND user_id = %s AND status = %s",
                               (product_id, session['user_id'], 'complete'))
                order = cursor.fetchone()
                if order:
                    return '1'  # show form
                else:
                    return '4'  # order is not complete
    else:
        print('not logged in')
        return '2'  # not logged in


@app.route('/rateProduct', methods=['GET', 'POST'])
def rate_product():
    if request.method == 'POST':
        product_id = request.form['rating_pid']
        rating = request.form['rating_p']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("INSERT INTO product_ratings(product_id, user_id, rating) VALUES(%s, %s, %s)",
                       (product_id, session['user_id'], rating))
        mysql.connection.commit()
        return redirect(url_for('index'))
    return redirect(url_for('index'))


def getProductRatingId(product_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM product_ratings WHERE product_id = %s", (product_id,))
    ratings = cur.fetchall()
    user_ratings = 0
    for rating in ratings:
        user_ratings += rating['rating']
    ratings_row_count = cur.rowcount
    if ratings_row_count == 0:
        return 1
    product_ratings = int(user_ratings / ratings_row_count)
    return product_ratings


app.jinja_env.globals.update(getProductRatingId=getProductRatingId)


@app.route('/addReview', methods=['GET', 'POST'])
def add_review():
    if 'user_loggedin' in session and session['user_loggedin']:
        if request.method == 'POST':
            product_id = request.form['product_id']
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * from product_reviews WHERE product_id = %s and user_id = %s",
                           (product_id, session['user_id']))
            data = cursor.fetchone()
            if data:
                return '3'  # already done
            else:
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("SELECT * FROM orders WHERE product_id = %s AND user_id = %s AND status = %s",
                               (product_id, session['user_id'], 'complete'))
                order = cursor.fetchone()
                if order:
                    return '1'  # show form
                else:
                    return '4'  # order is not complete
    else:
        print('not logged in')
        return '2'  # not logged in


@app.route('/reviewProduct', methods=['GET', 'POST'])
def review_product():
    if request.method == 'POST':
        product_id = request.form['review_pid']
        review = request.form['review_p']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("INSERT INTO product_reviews(product_id, user_id, review) VALUES(%s, %s, %s)",
                       (product_id, session['user_id'], review))
        mysql.connection.commit()
        return redirect(url_for('index'))
    return redirect(url_for('index'))


def getProductReviewId(product_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM product_reviews WHERE product_id = %s", (product_id,))
    reviews = cur.fetchall()
    reviews_row_count = cur.rowcount
    return reviews, reviews_row_count


app.jinja_env.globals.update(getProductReviewId=getProductReviewId)


@app.route('/logout')
def logout():
    session.pop('user_loggedin', None)
    session.pop('user_email', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))




@app.route('/cart', methods=['GET', 'POST'])
def cart():
    if 'user_loggedin' in session and session['user_loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user_cart WHERE user_id = %s", (session['user_id'],))
        items = cursor.fetchall()

        # Fetching product IDs and their total quantities
        cursor.execute("SELECT id, total FROM products")
        product_data = cursor.fetchall()

        print_data = []  # List to store print statement data

        product_quantities = {}  # Dictionary to store product ID and total quantity
        for row in product_data:
            product_id = row['id']
            total_quantity = row['total']
            product_quantities[product_id] = total_quantity

        # Fetching orders and calculating the total number of orders for each product
        product_orders = {}  # Dictionary to store product ID and order count
        for product_id, total_quantity in product_quantities.items():
            cursor.execute("SELECT COUNT(*) AS order_count FROM orders WHERE product_id = %s", (product_id,))
            order_count_data = cursor.fetchone()
            order_count = order_count_data['order_count']
            product_orders[product_id] = order_count

            cursor.execute("SELECT SUM(quantity) AS sold_quantity FROM user_transactions WHERE product_id = %s", (product_id,))
            sold_quantity_data = cursor.fetchone()
            sold_quantity = sold_quantity_data['sold_quantity']
            if sold_quantity is None:
                sold_quantity = 0  # If no transactions found, set sold quantity to 0

            print(f"Product ID: {product_id}, Total Product: {total_quantity}, Sold Product: {sold_quantity}, Orders: {order_count}, Available: {total_quantity - sold_quantity}")
            print_data.append({
                "product_id": product_id,
                "total_quantity": total_quantity,
                "sold_quantity": sold_quantity,
                "order_count": order_count,
                "available": total_quantity - sold_quantity
            })

            # Update the availability status in the products table
            available_quantity = total_quantity - sold_quantity

            cursor.execute("UPDATE products SET avalible=%s, sold=%s WHERE id=%s", (available_quantity, sold_quantity, product_id))

        total_available = sum(product_quantities.values())

        if items:
            return render_template('cart.html', items=items, item_count=len(items), total_available=available_quantity, product_quantities=product_quantities, print_data=print_data)
        else:
            return render_template('cart.html', cartmsg='There are not items in your cart.', item_count=len(items), total_available=available_quantity, product_quantities=product_quantities)
    else:
        return redirect(url_for('login'))





@app.route('/setCartItemQuantity', methods=['GET', 'POST'])
def setCartItemQuantity():
    if request.method == 'POST':
        product_id = request.form['product_id']
        quantity = request.form['quantity']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("UPDATE user_cart SET quantity = %s WHERE product_id = %s AND user_id = %s",
                       (quantity, product_id, session['user_id']))
        mysql.connection.commit()
        total_cart_items = userCartItems()
        return jsonify(total_cart_items=total_cart_items)


@app.route('/removeCartItem', methods=['GET', 'POST'])
def removeCartItem():
    if request.method == 'POST':
        product_id = request.form['product_id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("DELETE FROM user_cart WHERE product_id = %s AND user_id = %s", (product_id, session['user_id']))
        mysql.connection.commit()
        status = '1'
        return jsonify(status=status)


@app.route('/buy', methods=['GET', 'POST'])
def buy():
    if 'user_loggedin' in session and session['user_loggedin']:
        if request.method == 'POST':
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM user_cart WHERE user_id = %s", (session['user_id'],))
            items = cursor.fetchall()
            alphanumeric_chars = string.ascii_letters + string.digits
            transaction_id = ''.join(random.choices(alphanumeric_chars, k=12))
            current_date = datetime.now().strftime('%d/%m/%Y')
            for item in items:
                item_data = getProductDataById(item['product_id'])
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute(
                    "INSERT INTO user_transactions (txn_id, user_id, product_id, quantity, date, status) VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                    transaction_id, session['user_id'], item['product_id'], item['quantity'], current_date, 'complete'))
                mysql.connection.commit()
                order_id = ''.join(random.choices(alphanumeric_chars, k=5))
                cursor.execute(
                    "INSERT INTO orders (order_id, txn_id, user_id, product_id, date, status) VALUES (%s, %s, %s, %s, %s, %s)",
                    (order_id, transaction_id, session['user_id'], item['product_id'], current_date, 'pending'))
                mysql.connection.commit()
                cursor.execute("DELETE FROM user_cart WHERE product_id = %s AND user_id = %s",
                               (item['product_id'], session['user_id']))
                mysql.connection.commit()
            return redirect(url_for('index', msg='Transaction has been completed successfully.'))
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user_cart WHERE user_id = %s", (session['user_id'],))
        cart_items_row_count = cursor.rowcount
        total_price = 0
        total_items = 0
        if cart_items_row_count:
            cart_data = cursor.fetchall()
            total_items = userCartItems()
            for item in cart_data:
                item_data = getProductDataById(item['product_id'])
                item_price = int(item_data['price']) * int(item['quantity'])
                total_price += item_price
            return render_template('buy.html', total_price=total_price, total_items=total_items)
    else:
        return redirect(url_for('login'))


@app.route('/transactions', methods=['GET', 'POST'])
def userTransactions():
    if 'user_loggedin' in session and session['user_loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user_transactions WHERE user_id = %s", (session['user_id'],))
        transactions = cursor.fetchall()
        transactions_count = cursor.rowcount
        print(transactions_count)
        return render_template('transaction-history.html', transactions=transactions,
                               transactions_count=transactions_count)
    else:
        return redirect(url_for('login'))


@app.route('/orders', methods=['GET', 'POST'])
def userOrders():
    if 'user_loggedin' in session and session['user_loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM orders WHERE user_id = %s", (session['user_id'],))
        orders = cursor.fetchall()
        orders_count = cursor.rowcount
        return render_template('orders.html', orders=orders, orders_count=orders_count)
    else:
        return redirect(url_for('login'))







if __name__ == '__main__':
    app.run(debug=True)  # Enable debug mode for development