import os
from werkzeug.security import generate_password_hash
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    return app

from models import User, Product, OrderStatus  # after db initialized

def seed_data(app):
    with app.app_context():
        db.create_all()

        if not db.session.query(User).filter_by(email="admin@example.com").first():
            admin = User(
                email="admin@example.com",
                name="Admin",
                role="admin",
                password_hash=generate_password_hash("AdminPass123!")
            )
            db.session.add(admin)

        if not db.session.query(User).filter_by(email="user@example.com").first():
            user = User(
                email="user@example.com",
                name="Regular User",
                role="user",
                password_hash=generate_password_hash("UserPass123!")
            )
            db.session.add(user)

        if db.session.query(Product).count() == 0:
            products = [
                Product(sku="P-1001", name="Aluminum Bracket", description="CNC-milled bracket", unit_price=12.50),
                Product(sku="P-1002", name="Steel Gear", description="Hardened gear", unit_price=34.00),
                Product(sku="P-1003", name="Plastic Housing", description="Injection-molded housing", unit_price=8.99),
                Product(sku="P-1004", name="Copper Coil", description="Precision-wound coil", unit_price=22.75),
                Product(sku="P-1005", name="Rubber Gasket", description="High-temp gasket", unit_price=3.50),
            ]
            db.session.add_all(products)

        db.session.commit()
        print("Database initialized and seeded.")

if __name__ == "__main__":
    app = create_app()
    seed_data(app)
