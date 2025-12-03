import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import DeclarativeBase
from config import Config

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"

    from models import User, Product, Order, OrderItem, OrderStatus
    from forms import RegisterForm, LoginForm, AddToCartForm, UpdateStatusForm

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = RegisterForm()
        if form.validate_on_submit():
            from models import User
            existing = db.session.query(User).filter_by(email=form.email.data.lower()).first()
            if existing:
                flash("Email already registered.", "warning")
                return redirect(url_for("login"))
            user = User(
                name=form.name.data.strip(),
                email=form.email.data.lower(),
                password_hash=generate_password_hash(form.password.data),
                role="user"
            )
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        return render_template("register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = LoginForm()
        if form.validate_on_submit():
            from models import User
            user = db.session.query(User).filter_by(email=form.email.data.lower()).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                flash("Logged in successfully.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid credentials.", "danger")
        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Logged out.", "info")
        return redirect(url_for("index"))

    def require_admin():
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)

    @app.route("/products", methods=["GET", "POST"])
    @login_required
    def products():
        from models import Product
        items = db.session.query(Product).filter_by(active=1).all()
        add_form = AddToCartForm()

        if request.method == "POST" and add_form.validate_on_submit():
            product_id = int(add_form.product_id.data)
            quantity = int(add_form.quantity.data)
            cart = session.get("cart", {})
            cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
            session["cart"] = cart
            flash("Added to cart.", "success")
            return redirect(url_for("products"))

        return render_template("products.html", products=items, add_form=add_form, cart=session.get("cart", {}))

    @app.route("/cart")
    @login_required
    def cart():
        from models import Product
        cart = session.get("cart", {})
        product_ids = [int(pid) for pid in cart.keys()]
        products = {}
        if product_ids:
            for p in db.session.query(Product).filter(Product.id.in_(product_ids)).all():
                products[p.id] = p
        total = 0.0
        for pid, qty in cart.items():
            p = products.get(int(pid))
            if p:
                total += p.unit_price * qty
        return render_template("cart.html", cart=cart, products=products, total=round(total, 2))

    @app.route("/cart/remove/<int:product_id>")
    @login_required
    def cart_remove(product_id):
        cart = session.get("cart", {})
        cart.pop(str(product_id), None)
        session["cart"] = cart
        return redirect(url_for("cart"))

    @app.route("/order/review", methods=["GET", "POST"])
    @login_required
    def order_review():
        from models import Product, Order, OrderItem, OrderStatus
        cart = session.get("cart", {})
        if not cart:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("products"))
        product_ids = [int(pid) for pid in cart.keys()]
        products = {p.id: p for p in db.session.query(Product).filter(Product.id.in_(product_ids)).all()}
        line_items = []
        total = 0.0
        for pid, qty in cart.items():
            p = products.get(int(pid))
            if p:
                line_items.append({"product": p, "quantity": qty, "unit_price": p.unit_price})
                total += p.unit_price * qty
        if request.method == "POST":
            order = Order(user_id=current_user.id)
            db.session.add(order)
            db.session.flush()
            for li in line_items:
                db.session.add(OrderItem(
                    order_id=order.id,
                    product_id=li["product"].id,
                    quantity=li["quantity"],
                    unit_price=li["unit_price"]
                ))
            db.session.commit()
            session["cart"] = {}
            flash("Order placed successfully.", "success")
            return redirect(url_for("dashboard"))
        return render_template("order_review.html", line_items=line_items, total=round(total, 2))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        from models import Order, OrderStatus
        orders = db.session.query(Order).filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
        return render_template("dashboard.html", orders=orders)

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        require_admin()
        from models import Order, OrderStatus
        orders = db.session.query(Order).order_by(Order.created_at.desc()).all()
        return render_template("admin_dashboard.html", orders=orders, statuses=[s.value for s in OrderStatus])

    @app.route("/admin/order/<int:order_id>", methods=["GET", "POST"])
    @login_required
    def admin_order_detail(order_id):
        require_admin()
        from models import Order, OrderItem, OrderStatus
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        form = UpdateStatusForm()
        if form.validate_on_submit():
            try:
                new_status = OrderStatus(form.status.data)
            except ValueError:
                flash("Invalid status.", "danger")
                return redirect(url_for("admin_order_detail", order_id=order_id))
            order.status = new_status
            order.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Order status updated.", "success")
            return redirect(url_for("admin_order_detail", order_id=order_id))
        return render_template("order_detail.html", order=order, form=form, statuses=[s.value for s in OrderStatus])

    return app

app = create_app()
