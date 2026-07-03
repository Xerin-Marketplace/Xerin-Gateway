# 🛒 Ecommerce Platform Backend

A scalable and modular **E-commerce backend system** built with a relational database design using **PostgreSQL**. This project focuses on building a robust foundation for an online shopping platform, including user management, product catalog, orders, payments, notifications, and system operations.

---

## 📌 Project Overview

This system is designed to power a full-featured e-commerce application. It supports:

- User authentication and role management
- Product catalog with categories, brands, and variants
- Shopping cart and order processing
- Payment handling with transaction tracking
- Inventory and warehouse management
- Notifications (SMS, Email, Push, System)
- Reviews and ratings
- System auditing and background job processing

---

## 🏗️ Database Architecture

The system is built on a **relational PostgreSQL schema** with well-structured relationships and normalization.

### Core Modules

#### 👤 User Management
- Users, roles, and permissions
- Sessions and OTP authentication
- Address management
- User status tracking (active, suspended, etc.)

#### 🛍️ Product Management
- Products with categories and brands
- Product images and variants
- Inventory tracking per warehouse
- Category hierarchy support

#### 🛒 Cart & Orders
- Shopping cart system
- Order creation and status tracking
- Order history and lifecycle management
- Coupon support for discounts

#### 💳 Payments
- Multiple payment methods support
- Payment transactions and callbacks
- Refund management
- Payment status tracking

#### 📦 Inventory System
- Warehouse-based stock management
- Reserved and available stock tracking

#### 🔔 Notifications & Communication
- Email and SMS messaging system
- In-app notifications
- Notification types (system, email, SMS, push)

#### ⭐ Reviews & Feedback
- Product ratings and reviews by users

#### 🧾 System Monitoring
- Audit logs for tracking system changes
- Background job queue system
- System event tracking

---

## 🧩 Key Features

- 🔐 Secure authentication system (sessions + OTP)
- 🛍️ Full product lifecycle management
- 📦 Multi-warehouse inventory support
- 💳 Flexible payment and refund system
- 📊 Order tracking with detailed status history
- 🔔 Multi-channel notification system
- 🧾 Audit logging for accountability
- ⚙️ Scalable job queue system for background tasks

---

## 📊 Order Flow

1. User adds products to cart
2. Cart is converted into an order
3. Order is assigned a status (`pending → paid → shipped → delivered`)
4. Payment is processed and recorded
5. Inventory is updated
6. Notifications are sent
7. Order history is tracked

---

## 🗄️ Technologies (Suggested Stack)

- PostgreSQL (Database)
- NFAST API (Backend API)
- Prisma / TypeORM (ORM)
- Redis (Caching / Queues)
- Docker (Deployment)
- JWT / Session Auth

---

## 🔗 Database Design Highlights

- Fully normalized relational schema
- UUID-based primary keys for scalability
- Strong foreign key relationships
- Enum-based status tracking
- Time-stamped records for auditing

---

## 📁 Main Entities

- `users`
- `products`
- `orders`
- `payments`
- `inventory`
- `carts`
- `categories`
- `notifications`
- `reviews`
- `audit_logs`

---

## 🚀 Future Improvements

- GraphQL API layer
- Microservices architecture
- Real-time order tracking (WebSockets)
- Recommendation engine
- Advanced analytics dashboard
- Multi-vendor marketplace support

---

## 👨‍💻 Purpose of This Project

This project is built as a **learning and production-ready backend architecture** for modern e-commerce systems. It demonstrates how large-scale platforms structure their databases and business logic.

---

## 📜 License

This project is open-source and available under the MIT License.

---

## 🤝 Contributions

Contributions, issues, and feature requests are welcome!

---

## 📬 Contact

If you have questions or suggestions, feel free to reach out.

```
ADAM KAtani
NAFIDH MOLA

```

# 1 USER AUTHENTICATION FLOW 

```
New User:
Register
↓
Verify OTP
↓
Get Tokens
↓
Use App

Returning User:
Login
↓
Get Tokens
↓
Use App
```


# SERVICES 

Auth Service
User Service
Seller Service
Product Service
Order Service
Payment Service
Logistics Service
Notification Service
Admin Service

# 1: AUTH FLOW 



# 3: SELLER FLOW 

```
1. Seller registers from auth page
   POST /auth/register-seller
   seller_status = pending

2. Seller logs in
   POST /auth/login

3. Frontend checks profile
   GET /users/me
   account_type = seller
   seller_status = pending

4. Frontend shows KYC upload page

5. Seller uploads:
   POST /sellers/kyc-documents
   document_type = tin

   POST /sellers/kyc-documents
   document_type = business_profile

   POST /sellers/kyc-documents
   document_type = business_registration

6. After all 3 documents are uploaded
   seller_status = under_review

7. Admin sees pending review sellers
   GET /sellers/admin/pending

8. Admin views documents
   GET /sellers/admin/{seller_id}/documents

9. Admin approves
   POST /sellers/admin/{seller_id}/approve

10. Seller status becomes approved

11. Seller can now create products

```

# RUN
```
uvicorn api.main:api --reload

```
# REDDIS 

```
pip install "redis>=5.0.0"
```

```
nano ~/.bashrc

```
```ex
port REDIS_URL=redis://localhost:6379/0

```
```
source ~/.bashrc

```

