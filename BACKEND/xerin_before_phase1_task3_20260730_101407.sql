--
-- PostgreSQL database dump
--

\restrict ForGPR5Us4D0r1sfSbniZHBohHqliuyqgHCfJKVvdbBc7h5LRkYuKfGddihoaaI

-- Dumped from database version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: postgres
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO postgres;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: dayofweek; Type: TYPE; Schema: public; Owner: app_user
--

CREATE TYPE public.dayofweek AS ENUM (
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday'
);


ALTER TYPE public.dayofweek OWNER TO app_user;

--
-- Name: orderstatus; Type: TYPE; Schema: public; Owner: app_user
--

CREATE TYPE public.orderstatus AS ENUM (
    'pending',
    'paid',
    'processing',
    'shipped',
    'delivered',
    'cancelled',
    'refunded'
);


ALTER TYPE public.orderstatus OWNER TO app_user;

--
-- Name: paymentmethod; Type: TYPE; Schema: public; Owner: app_user
--

CREATE TYPE public.paymentmethod AS ENUM (
    'mobile_money',
    'bank_transfer',
    'card',
    'cash_on_delivery',
    'xerin_pay'
);


ALTER TYPE public.paymentmethod OWNER TO app_user;

--
-- Name: paymentstatus; Type: TYPE; Schema: public; Owner: app_user
--

CREATE TYPE public.paymentstatus AS ENUM (
    'pending',
    'processing',
    'completed',
    'failed',
    'refunded',
    'cancelled'
);


ALTER TYPE public.paymentstatus OWNER TO app_user;

--
-- Name: productstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.productstatus AS ENUM (
    'draft',
    'pending_review',
    'approved',
    'rejected',
    'inactive'
);


ALTER TYPE public.productstatus OWNER TO postgres;

--
-- Name: sellerstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.sellerstatus AS ENUM (
    'pending',
    'under_review',
    'approved',
    'rejected',
    'suspended'
);


ALTER TYPE public.sellerstatus OWNER TO postgres;

--
-- Name: storestatus; Type: TYPE; Schema: public; Owner: app_user
--

CREATE TYPE public.storestatus AS ENUM (
    'draft',
    'active',
    'closed',
    'suspended'
);


ALTER TYPE public.storestatus OWNER TO app_user;

--
-- Name: userstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.userstatus AS ENUM (
    'active',
    'inactive',
    'suspended',
    'pending_verification'
);


ALTER TYPE public.userstatus OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: addresses; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.addresses (
    id uuid NOT NULL,
    user_id uuid,
    country character varying(100),
    region character varying(100),
    city character varying(100),
    street text,
    postal_code character varying(50),
    is_default boolean,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.addresses OWNER TO app_user;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO app_user;

--
-- Name: brands; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.brands (
    id uuid NOT NULL,
    name character varying(150) NOT NULL,
    slug character varying(150) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.brands OWNER TO app_user;

--
-- Name: business_categories; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.business_categories (
    id uuid NOT NULL,
    name character varying(150) NOT NULL,
    slug character varying(150),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.business_categories OWNER TO app_user;

--
-- Name: cart_items; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.cart_items (
    id uuid NOT NULL,
    cart_id uuid NOT NULL,
    product_id uuid NOT NULL,
    variant_id uuid,
    quantity integer NOT NULL,
    unit_price numeric(18,2) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.cart_items OWNER TO app_user;

--
-- Name: carts; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.carts (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    coupon_code character varying(50),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.carts OWNER TO app_user;

--
-- Name: categories; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.categories (
    id uuid NOT NULL,
    parent_id uuid,
    name character varying(150) NOT NULL,
    slug character varying(150) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.categories OWNER TO app_user;

--
-- Name: coupons; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.coupons (
    id uuid NOT NULL,
    code character varying(50) NOT NULL,
    description text,
    discount_type character varying(20) NOT NULL,
    discount_value numeric(18,2) NOT NULL,
    minimum_order_amount numeric(18,2),
    maximum_discount_amount numeric(18,2),
    usage_limit integer,
    usage_count integer NOT NULL,
    is_active boolean,
    valid_from timestamp with time zone,
    valid_until timestamp with time zone,
    created_by_id uuid,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.coupons OWNER TO app_user;

--
-- Name: inventory; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.inventory (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    variant_id uuid,
    quantity integer NOT NULL,
    reserved_quantity integer NOT NULL,
    available_quantity integer NOT NULL,
    warehouse_location character varying(255),
    low_stock_threshold integer,
    restock_date timestamp with time zone,
    updated_at timestamp with time zone,
    updated_by_id uuid
);


ALTER TABLE public.inventory OWNER TO app_user;

--
-- Name: order_items; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.order_items (
    id uuid NOT NULL,
    order_id uuid NOT NULL,
    product_id uuid NOT NULL,
    variant_id uuid,
    seller_id uuid NOT NULL,
    product_name character varying(255) NOT NULL,
    variant_name character varying(100),
    quantity integer NOT NULL,
    unit_price numeric(18,2) NOT NULL,
    total_price numeric(18,2) NOT NULL
);


ALTER TABLE public.order_items OWNER TO app_user;

--
-- Name: order_status_history; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.order_status_history (
    id uuid NOT NULL,
    order_id uuid NOT NULL,
    status character varying(50) NOT NULL,
    notes text,
    created_by_id uuid,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.order_status_history OWNER TO app_user;

--
-- Name: orders; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.orders (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    shipping_address_id uuid,
    status public.orderstatus NOT NULL,
    currency character varying(10) NOT NULL,
    subtotal numeric(18,2) NOT NULL,
    discount_amount numeric(18,2) NOT NULL,
    shipping_amount numeric(18,2) NOT NULL,
    tax_amount numeric(18,2) NOT NULL,
    total numeric(18,2) NOT NULL,
    coupon_code character varying(50),
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.orders OWNER TO app_user;

--
-- Name: otp_requests; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.otp_requests (
    id uuid NOT NULL,
    user_id uuid,
    phone character varying(30),
    otp_code character varying(10),
    expires_at timestamp with time zone,
    verified boolean,
    created_at timestamp with time zone DEFAULT now(),
    purpose character varying(50) DEFAULT 'generic'::character varying
);


ALTER TABLE public.otp_requests OWNER TO app_user;

--
-- Name: payment_transactions; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.payment_transactions (
    id uuid NOT NULL,
    payment_id uuid NOT NULL,
    transaction_type character varying(50) NOT NULL,
    status character varying(50) NOT NULL,
    amount numeric(18,2),
    provider_response jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.payment_transactions OWNER TO app_user;

--
-- Name: payments; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.payments (
    id uuid NOT NULL,
    order_id uuid NOT NULL,
    user_id uuid NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency character varying(10) NOT NULL,
    method public.paymentmethod NOT NULL,
    provider character varying(100),
    status public.paymentstatus NOT NULL,
    provider_transaction_id character varying(255),
    provider_response jsonb,
    failure_reason text,
    paid_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.payments OWNER TO app_user;

--
-- Name: permissions; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.permissions (
    id uuid NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(150) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.permissions OWNER TO app_user;

--
-- Name: product_images; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.product_images (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    image_url text NOT NULL,
    is_primary boolean,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.product_images OWNER TO app_user;

--
-- Name: product_tags; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.product_tags (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    tag character varying(100) NOT NULL
);


ALTER TABLE public.product_tags OWNER TO app_user;

--
-- Name: product_variants; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.product_variants (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    variant_name character varying(100) NOT NULL,
    sku character varying(100) NOT NULL,
    price numeric(18,2),
    attributes jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.product_variants OWNER TO app_user;

--
-- Name: products; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.products (
    id uuid NOT NULL,
    seller_id uuid NOT NULL,
    category_id uuid NOT NULL,
    brand_id uuid,
    sku character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(255) NOT NULL,
    description text,
    price numeric(18,2) NOT NULL,
    sale_price numeric(18,2),
    currency character varying(10),
    weight numeric(10,2),
    status public.productstatus,
    rejection_reason text,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.products OWNER TO app_user;

--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.role_permissions (
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL
);


ALTER TABLE public.role_permissions OWNER TO app_user;

--
-- Name: roles; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.roles (
    id uuid NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.roles OWNER TO app_user;

--
-- Name: seller_business_categories; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.seller_business_categories (
    id uuid NOT NULL,
    seller_id uuid NOT NULL,
    category_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.seller_business_categories OWNER TO app_user;

--
-- Name: seller_kyc_documents; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.seller_kyc_documents (
    id uuid NOT NULL,
    seller_id uuid NOT NULL,
    document_type character varying(100) NOT NULL,
    document_url text NOT NULL,
    status character varying(50),
    rejection_reason text,
    uploaded_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.seller_kyc_documents OWNER TO app_user;

--
-- Name: seller_payout_accounts; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.seller_payout_accounts (
    id uuid NOT NULL,
    seller_id uuid NOT NULL,
    account_type character varying(50) NOT NULL,
    provider character varying(100) NOT NULL,
    account_name character varying(255) NOT NULL,
    account_number character varying(255) NOT NULL,
    currency character varying(10),
    is_default boolean,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.seller_payout_accounts OWNER TO app_user;

--
-- Name: seller_profiles; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.seller_profiles (
    id uuid NOT NULL,
    seller_id uuid NOT NULL,
    business_description text,
    business_country character varying(100),
    business_region character varying(100),
    business_city character varying(100),
    business_address text,
    product_description text,
    years_in_business character varying(50),
    website_url text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.seller_profiles OWNER TO app_user;

--
-- Name: sellers; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.sellers (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    business_name character varying(255) NOT NULL,
    business_category character varying(150),
    contact_email character varying(255),
    contact_phone character varying(30),
    status public.sellerstatus,
    agreement_accepted boolean,
    approved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.sellers OWNER TO app_user;

--
-- Name: sessions; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.sessions (
    id uuid NOT NULL,
    user_id uuid,
    refresh_token text NOT NULL,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.sessions OWNER TO app_user;

--
-- Name: store_gallery_images; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.store_gallery_images (
    id uuid NOT NULL,
    store_id uuid NOT NULL,
    image_url text NOT NULL,
    caption character varying(255),
    display_order integer NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.store_gallery_images OWNER TO app_user;

--
-- Name: store_opening_hours; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.store_opening_hours (
    id uuid NOT NULL,
    store_id uuid NOT NULL,
    day_of_week public.dayofweek NOT NULL,
    day_number integer NOT NULL,
    open_time time without time zone,
    close_time time without time zone,
    is_closed boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.store_opening_hours OWNER TO app_user;

--
-- Name: stores; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.stores (
    id uuid NOT NULL,
    seller_id uuid NOT NULL,
    store_name character varying(255) NOT NULL,
    slug character varying(255) NOT NULL,
    description text,
    logo_url text,
    banner_url text,
    contact_email character varying(255),
    contact_phone character varying(30),
    website_url text,
    country character varying(100),
    region character varying(100),
    district character varying(100),
    ward character varying(100),
    street text,
    latitude double precision,
    longitude double precision,
    opening_time time without time zone,
    closing_time time without time zone,
    shipping_policy text,
    return_policy text,
    privacy_policy text,
    facebook_url text,
    instagram_url text,
    twitter_url text,
    tiktok_url text,
    youtube_url text,
    status public.storestatus NOT NULL,
    is_verified boolean NOT NULL,
    is_featured boolean NOT NULL,
    rating numeric(3,2) NOT NULL,
    review_count integer NOT NULL,
    followers_count integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.stores OWNER TO app_user;

--
-- Name: user_permissions; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.user_permissions (
    user_id uuid NOT NULL,
    permission_id uuid NOT NULL
);


ALTER TABLE public.user_permissions OWNER TO app_user;

--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.user_roles (
    user_id uuid NOT NULL,
    role_id uuid NOT NULL
);


ALTER TABLE public.user_roles OWNER TO app_user;

--
-- Name: users; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    first_name character varying(100),
    last_name character varying(100),
    email character varying(255) NOT NULL,
    phone character varying(30),
    password_hash text NOT NULL,
    status public.userstatus,
    is_verified boolean,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.users OWNER TO app_user;

--
-- Data for Name: addresses; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.addresses (id, user_id, country, region, city, street, postal_code, is_default, created_at) FROM stdin;
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.alembic_version (version_num) FROM stdin;
add_otp_purpose
\.


--
-- Data for Name: brands; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.brands (id, name, slug, created_at) FROM stdin;
\.


--
-- Data for Name: business_categories; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.business_categories (id, name, slug, created_at) FROM stdin;
\.


--
-- Data for Name: cart_items; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.cart_items (id, cart_id, product_id, variant_id, quantity, unit_price, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: carts; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.carts (id, user_id, coupon_code, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.categories (id, parent_id, name, slug, created_at) FROM stdin;
\.


--
-- Data for Name: coupons; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.coupons (id, code, description, discount_type, discount_value, minimum_order_amount, maximum_discount_amount, usage_limit, usage_count, is_active, valid_from, valid_until, created_by_id, created_at) FROM stdin;
\.


--
-- Data for Name: inventory; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.inventory (id, product_id, variant_id, quantity, reserved_quantity, available_quantity, warehouse_location, low_stock_threshold, restock_date, updated_at, updated_by_id) FROM stdin;
\.


--
-- Data for Name: order_items; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.order_items (id, order_id, product_id, variant_id, seller_id, product_name, variant_name, quantity, unit_price, total_price) FROM stdin;
\.


--
-- Data for Name: order_status_history; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.order_status_history (id, order_id, status, notes, created_by_id, created_at) FROM stdin;
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.orders (id, user_id, shipping_address_id, status, currency, subtotal, discount_amount, shipping_amount, tax_amount, total, coupon_code, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: otp_requests; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.otp_requests (id, user_id, phone, otp_code, expires_at, verified, created_at, purpose) FROM stdin;
9ca8e50c-f9e7-4e8f-bd9c-8e2576f2b57c	08823972-8709-402a-8227-971e755526e5	+255694021848	359393	2026-06-28 13:52:39.683641+03	t	2026-06-28 13:47:39.682197+03	generic
b7e51777-e0e5-46a5-8965-7a07064d2549	189d5f98-ec3f-4a87-91e5-0503d0c298d9	+255635673730	569804	2026-06-28 15:23:28.098452+03	f	2026-06-28 15:18:28.095301+03	generic
3da823d6-a1fc-4627-989c-638f92114d7b	1e46cf5a-35f7-4892-bcd4-06e3007ef1e9	+255635673750	333485	2026-06-28 15:28:05.260763+03	f	2026-06-28 15:23:05.259485+03	generic
4592d03e-0f2e-4335-a61a-c09745eef527	c2494096-838e-4a5f-9e53-928ce92cba4b	+255635673740	350590	2026-06-28 15:31:48.070862+03	f	2026-06-28 15:26:48.069721+03	generic
3811959d-4693-4503-9f6f-11e3a4e6e53a	d208edeb-ebd8-4b9e-842d-12de37498c15	+255635673732	916881	2026-06-28 15:35:04.212053+03	f	2026-06-28 15:30:04.211022+03	generic
00169298-74db-457e-8d2d-b10f42b5203b	54aa6291-1df5-4d9e-8c17-78d7082f58a4	+255624909756	156239	2026-06-28 15:38:50.433146+03	f	2026-06-28 15:33:50.432204+03	generic
842af646-72d4-4ced-a8b5-37a9192413da	5d979c0c-f753-4471-944c-b4ff94f00af5	+255682303730	108841	2026-06-28 15:40:13.800206+03	f	2026-06-28 15:35:13.798439+03	generic
bbc1f1ad-558d-4db1-9adc-69d94eeb4ec9	68f19246-216b-4162-af0c-968cb58c714a	+255613976254	570301	2026-06-28 15:44:24.815182+03	f	2026-06-28 15:39:24.814097+03	generic
3da1b60a-ee3d-4d08-bab2-46124d52b8a7	979ed518-5054-4cc5-9582-05c68b51631b	+255767939800	673244	2026-06-29 15:48:35.481224+03	f	2026-06-29 15:43:35.476908+03	generic
29932a2b-74b8-4730-9c87-b46833c735df	6ea435b0-a945-45bd-ab29-fce4af3e29e3	+255767939809	448307	2026-06-27 20:35:33.751883+03	t	2026-06-27 20:30:33.745321+03	generic
92678bd5-7bb9-48a7-920e-e35b209bcff6	\N	+255767939809	167173	2026-07-03 14:44:10.848127+03	t	2026-07-03 14:39:10.833459+03	generic
\.


--
-- Data for Name: payment_transactions; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.payment_transactions (id, payment_id, transaction_type, status, amount, provider_response, created_at) FROM stdin;
\.


--
-- Data for Name: payments; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.payments (id, order_id, user_id, amount, currency, method, provider, status, provider_transaction_id, provider_response, failure_reason, paid_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.permissions (id, code, name, description, created_at) FROM stdin;
2f1ffd03-b1d4-4e51-9309-9049e4a32de2	view_profile	View Profile	Allows user to view profile	2026-07-03 15:59:21.398281+03
5b13d0c9-e72e-4169-8f5b-e3dcc00080b2	update_profile	Update Profile	Allows user to update profile	2026-07-03 15:59:21.398281+03
ee18f7cd-c683-4500-9e7f-81c0567a2c4f	manage_addresses	Manage Addresses	Allows user to manage addresses	2026-07-03 15:59:21.398281+03
d9a6cf8c-99ae-434e-8809-db6157eb0dd2	view_seller_profile	View Seller Profile	Allows user to view seller profile	2026-07-03 15:59:21.398281+03
d230d8f8-0310-45c5-a781-50f35b2e2da5	update_seller_profile	Update Seller Profile	Allows user to update seller profile	2026-07-03 15:59:21.398281+03
ef77b195-e306-4ffd-b559-ae1717123070	upload_kyc	Upload Kyc	Allows user to upload kyc	2026-07-03 15:59:21.398281+03
3613d35e-4bd8-4843-9b92-07a32975dd1b	manage_payout_accounts	Manage Payout Accounts	Allows user to manage payout accounts	2026-07-03 15:59:21.398281+03
cdc02065-a0bc-4381-bc5e-939441dce661	manage_products	Manage Products	Allows user to manage products	2026-07-03 15:59:21.398281+03
203799b3-78e4-4735-ada0-9623445e37fe	view_products	View Products	Allows user to view products	2026-07-03 15:59:21.398281+03
b40479b1-3bda-4b8a-b99c-89a2ffb37a34	manage_users	Manage Users	Allows user to manage users	2026-07-03 15:59:21.398281+03
073e37a9-5a1d-4966-b802-eb4490e50f24	manage_admins	Manage Admins	Allows user to manage admins	2026-07-03 15:59:21.398281+03
03501869-e6fd-48f0-a4df-2c8fcdb5b088	manage_business_categories	Manage Business Categories	Allows user to manage business categories	2026-07-03 15:59:21.398281+03
227b56d4-6fff-48aa-a6bd-7e17c5d3ae03	manage_product_categories	Manage Product Categories	Allows user to manage product categories	2026-07-03 15:59:21.398281+03
e91a6013-5067-48a4-919c-0b72379be7e1	manage_brands	Manage Brands	Allows user to manage brands	2026-07-03 15:59:21.398281+03
33699896-7291-4c00-b61b-cc1beaa1a5b1	approve_sellers	Approve Sellers	Allows user to approve sellers	2026-07-03 15:59:21.398281+03
69f81434-d04c-4bd1-8b1a-15f62a4706f2	reject_sellers	Reject Sellers	Allows user to reject sellers	2026-07-03 15:59:21.398281+03
46e3403a-698b-40a2-aafe-75e56096454e	view_sellers	View Sellers	Allows user to view sellers	2026-07-03 15:59:21.398281+03
9f47edc2-efd8-4c0c-bb5f-e4b3af3ba1c6	approve_products	Approve Products	Allows user to approve products	2026-07-03 15:59:21.398281+03
eb294fa3-0e13-4410-877a-6db1321e74e0	reject_products	Reject Products	Allows user to reject products	2026-07-03 15:59:21.398281+03
35b3b3bc-f40e-4fb7-8c94-6ebebf24e17d	manage_orders	Manage Orders	Allows user to manage orders	2026-07-03 15:59:21.398281+03
de2f57c0-6894-41d1-94db-99d794c8c0d5	view_reports	View Reports	Allows user to view reports	2026-07-03 15:59:21.398281+03
b9663630-209d-4385-b90c-c5c2eda7ad92	view_all_users	View All Users	Allows user to view all users	2026-07-03 16:31:44.353148+03
a617d881-0c88-4fa3-9374-492a407bebdd	can_create_users	Can Create Users	Allows user to can create users	2026-07-03 16:31:44.353148+03
f9494a84-1259-4fb4-aa3a-6247c9271915	can_view_users	Can View Users	Allows user to can view users	2026-07-03 16:31:44.353148+03
7269b34a-aab5-4c99-bc87-6444ab9ffee0	can_update_users	Can Update Users	Allows user to can update users	2026-07-03 16:31:44.353148+03
0154f98c-e03f-46e8-a129-49d71870562c	can_delete_users	Can Delete Users	Allows user to can delete users	2026-07-03 16:31:44.353148+03
7ced697a-5488-40ab-810a-216a72ffa556	can_create_admin_users	Can Create Admin Users	Allows user to can create admin users	2026-07-03 16:31:44.353148+03
2fcfa18c-c217-45e4-9c0e-ff3f5a68afb7	can_create_business_categories	Can Create Business Categories	Allows user to can create business categories	2026-07-03 16:31:44.353148+03
e32edeb4-b386-457b-b2b5-fb935e437a71	can_view_business_categories	Can View Business Categories	Allows user to can view business categories	2026-07-03 16:31:44.353148+03
960d880a-ae58-4225-aac0-f35abb74eb4e	can_update_business_categories	Can Update Business Categories	Allows user to can update business categories	2026-07-03 16:31:44.353148+03
dad7ffe5-7f7b-4e20-9583-379423ca4d8d	can_delete_business_categories	Can Delete Business Categories	Allows user to can delete business categories	2026-07-03 16:31:44.353148+03
cbca3d32-cc4c-497c-a42b-f7084605ef85	can_create_product_categories	Can Create Product Categories	Allows user to can create product categories	2026-07-03 16:31:44.353148+03
f006405d-4845-4300-8e9f-2247efcfccc8	can_view_product_categories	Can View Product Categories	Allows user to can view product categories	2026-07-03 16:31:44.353148+03
c1d0a960-e4e5-4a14-8654-36cefbf12ae5	can_delete_product_categories	Can Delete Product Categories	Allows user to can delete product categories	2026-07-03 16:31:44.353148+03
2936cce0-2120-4229-8a51-7c80c357309f	can_create_brands	Can Create Brands	Allows user to can create brands	2026-07-03 16:31:44.353148+03
d04f7dc7-5def-4e6b-8c35-f78fc9e7d101	can_view_brands	Can View Brands	Allows user to can view brands	2026-07-03 16:31:44.353148+03
380e077e-aed6-4975-94c0-96ee813401d2	can_delete_brands	Can Delete Brands	Allows user to can delete brands	2026-07-03 16:31:44.353148+03
58ae89ef-437f-4450-99a5-e05840b03db6	can_view_sellers	Can View Sellers	Allows user to can view sellers	2026-07-03 16:31:44.353148+03
613337b8-35c6-4bf9-b3a4-125e704047f3	can_view_pending_sellers	Can View Pending Sellers	Allows user to can view pending sellers	2026-07-03 16:31:44.353148+03
e7e6e117-7516-42e7-b878-5ec53cbabcbb	can_view_seller_documents	Can View Seller Documents	Allows user to can view seller documents	2026-07-03 16:31:44.353148+03
c10f4b8b-5dde-4961-8540-dd194ae8ee99	can_approve_sellers	Can Approve Sellers	Allows user to can approve sellers	2026-07-03 16:31:44.353148+03
556db563-15fe-48d2-acf9-326df71ee669	can_reject_sellers	Can Reject Sellers	Allows user to can reject sellers	2026-07-03 16:31:44.353148+03
c71044ea-9ea4-4fc9-9c8c-cb5a1e036366	can_view_products	Can View Products	Allows user to can view products	2026-07-03 16:31:44.353148+03
fee169b8-4a8f-4194-a0d1-ae5dba696003	can_approve_products	Can Approve Products	Allows user to can approve products	2026-07-03 16:31:44.353148+03
b12fbc10-976b-4238-b553-d1133ac19472	can_reject_products	Can Reject Products	Allows user to can reject products	2026-07-03 16:31:44.353148+03
004b2f72-5a84-44d9-b4cd-f0ac3f4b1067	can_assign_permissions	Can Assign Permissions	Allows user to can assign permissions	2026-07-15 15:53:12.043056+03
f724ad5a-759c-49a9-ad2b-7ed395421558	orders:read	Orders:Read	Allows user to orders:read	2026-07-15 15:53:12.043056+03
b0e2618e-6f82-41e6-afa4-126e3f674646	payments:read	Payments:Read	Allows user to payments:read	2026-07-15 15:53:12.043056+03
b2adffb2-fd73-4c20-8e51-0fc291b0adda	inventory:manage	Inventory:Manage	Allows user to inventory:manage	2026-07-15 15:53:12.043056+03
1930c1a6-2cf9-4e15-8cc0-00737a02a2e1	coupons:write	Coupons:Write	Allows user to coupons:write	2026-07-15 15:53:12.043056+03
c17b131a-c21b-4299-8974-eca0509f689f	coupons:read	Coupons:Read	Allows user to coupons:read	2026-07-15 15:53:12.043056+03
b7d33eb6-eb8b-4174-a853-9a829f8e4157	view_own_store	View Own Store	Allows user to view own store	2026-07-15 15:53:12.043056+03
adc668ef-f961-4dac-8128-a3190d5bdd96	update_own_store	Update Own Store	Allows user to update own store	2026-07-15 15:53:12.043056+03
38b90140-4da2-4569-9e0b-fd20da7bf8aa	upload_store_logo	Upload Store Logo	Allows user to upload store logo	2026-07-15 15:53:12.043056+03
1f81372f-f28c-4f9a-9c36-a480696d4530	upload_store_banner	Upload Store Banner	Allows user to upload store banner	2026-07-15 15:53:12.043056+03
546ac530-c25c-4739-8a01-b3fd5f99e057	view_public_stores	View Public Stores	Allows user to view public stores	2026-07-15 15:53:12.043056+03
589bf6b8-158c-439e-b9c8-62d65cd8a1a9	manage_all_stores	Manage All Stores	Allows user to manage all stores	2026-07-15 15:53:12.043056+03
94f2af0f-0331-4903-92a8-b36f2270bedf	can_view_public_stores	Can View Public Stores	Allows user to can view public stores	2026-07-15 16:14:59.801554+03
\.


--
-- Data for Name: product_images; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.product_images (id, product_id, image_url, is_primary, created_at) FROM stdin;
\.


--
-- Data for Name: product_tags; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.product_tags (id, product_id, tag) FROM stdin;
\.


--
-- Data for Name: product_variants; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.product_variants (id, product_id, variant_name, sku, price, attributes, created_at) FROM stdin;
\.


--
-- Data for Name: products; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.products (id, seller_id, category_id, brand_id, sku, name, slug, description, price, sale_price, currency, weight, status, rejection_reason, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.role_permissions (role_id, permission_id) FROM stdin;
d2184a82-f206-40f8-9ebf-172c6ec8a669	2f1ffd03-b1d4-4e51-9309-9049e4a32de2
d2184a82-f206-40f8-9ebf-172c6ec8a669	5b13d0c9-e72e-4169-8f5b-e3dcc00080b2
d2184a82-f206-40f8-9ebf-172c6ec8a669	ee18f7cd-c683-4500-9e7f-81c0567a2c4f
d2184a82-f206-40f8-9ebf-172c6ec8a669	203799b3-78e4-4735-ada0-9623445e37fe
3d11028b-8857-42b7-b96a-c557822ce9ab	2f1ffd03-b1d4-4e51-9309-9049e4a32de2
3d11028b-8857-42b7-b96a-c557822ce9ab	5b13d0c9-e72e-4169-8f5b-e3dcc00080b2
3d11028b-8857-42b7-b96a-c557822ce9ab	ee18f7cd-c683-4500-9e7f-81c0567a2c4f
3d11028b-8857-42b7-b96a-c557822ce9ab	d9a6cf8c-99ae-434e-8809-db6157eb0dd2
3d11028b-8857-42b7-b96a-c557822ce9ab	d230d8f8-0310-45c5-a781-50f35b2e2da5
3d11028b-8857-42b7-b96a-c557822ce9ab	ef77b195-e306-4ffd-b559-ae1717123070
3d11028b-8857-42b7-b96a-c557822ce9ab	3613d35e-4bd8-4843-9b92-07a32975dd1b
3d11028b-8857-42b7-b96a-c557822ce9ab	cdc02065-a0bc-4381-bc5e-939441dce661
3d11028b-8857-42b7-b96a-c557822ce9ab	203799b3-78e4-4735-ada0-9623445e37fe
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	2f1ffd03-b1d4-4e51-9309-9049e4a32de2
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	5b13d0c9-e72e-4169-8f5b-e3dcc00080b2
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	b40479b1-3bda-4b8a-b99c-89a2ffb37a34
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	03501869-e6fd-48f0-a4df-2c8fcdb5b088
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	227b56d4-6fff-48aa-a6bd-7e17c5d3ae03
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	e91a6013-5067-48a4-919c-0b72379be7e1
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	46e3403a-698b-40a2-aafe-75e56096454e
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	33699896-7291-4c00-b61b-cc1beaa1a5b1
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	69f81434-d04c-4bd1-8b1a-15f62a4706f2
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	9f47edc2-efd8-4c0c-bb5f-e4b3af3ba1c6
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	eb294fa3-0e13-4410-877a-6db1321e74e0
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	de2f57c0-6894-41d1-94db-99d794c8c0d5
2e02981f-ea08-431d-b154-525ac1730aba	2f1ffd03-b1d4-4e51-9309-9049e4a32de2
2e02981f-ea08-431d-b154-525ac1730aba	5b13d0c9-e72e-4169-8f5b-e3dcc00080b2
2e02981f-ea08-431d-b154-525ac1730aba	ee18f7cd-c683-4500-9e7f-81c0567a2c4f
2e02981f-ea08-431d-b154-525ac1730aba	d9a6cf8c-99ae-434e-8809-db6157eb0dd2
2e02981f-ea08-431d-b154-525ac1730aba	d230d8f8-0310-45c5-a781-50f35b2e2da5
2e02981f-ea08-431d-b154-525ac1730aba	ef77b195-e306-4ffd-b559-ae1717123070
2e02981f-ea08-431d-b154-525ac1730aba	3613d35e-4bd8-4843-9b92-07a32975dd1b
2e02981f-ea08-431d-b154-525ac1730aba	cdc02065-a0bc-4381-bc5e-939441dce661
2e02981f-ea08-431d-b154-525ac1730aba	203799b3-78e4-4735-ada0-9623445e37fe
2e02981f-ea08-431d-b154-525ac1730aba	b40479b1-3bda-4b8a-b99c-89a2ffb37a34
2e02981f-ea08-431d-b154-525ac1730aba	073e37a9-5a1d-4966-b802-eb4490e50f24
2e02981f-ea08-431d-b154-525ac1730aba	03501869-e6fd-48f0-a4df-2c8fcdb5b088
2e02981f-ea08-431d-b154-525ac1730aba	227b56d4-6fff-48aa-a6bd-7e17c5d3ae03
2e02981f-ea08-431d-b154-525ac1730aba	e91a6013-5067-48a4-919c-0b72379be7e1
2e02981f-ea08-431d-b154-525ac1730aba	33699896-7291-4c00-b61b-cc1beaa1a5b1
2e02981f-ea08-431d-b154-525ac1730aba	69f81434-d04c-4bd1-8b1a-15f62a4706f2
2e02981f-ea08-431d-b154-525ac1730aba	46e3403a-698b-40a2-aafe-75e56096454e
2e02981f-ea08-431d-b154-525ac1730aba	9f47edc2-efd8-4c0c-bb5f-e4b3af3ba1c6
2e02981f-ea08-431d-b154-525ac1730aba	eb294fa3-0e13-4410-877a-6db1321e74e0
2e02981f-ea08-431d-b154-525ac1730aba	35b3b3bc-f40e-4fb7-8c94-6ebebf24e17d
2e02981f-ea08-431d-b154-525ac1730aba	de2f57c0-6894-41d1-94db-99d794c8c0d5
d2184a82-f206-40f8-9ebf-172c6ec8a669	c71044ea-9ea4-4fc9-9c8c-cb5a1e036366
3d11028b-8857-42b7-b96a-c557822ce9ab	c71044ea-9ea4-4fc9-9c8c-cb5a1e036366
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	e32edeb4-b386-457b-b2b5-fb935e437a71
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	f006405d-4845-4300-8e9f-2247efcfccc8
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	d04f7dc7-5def-4e6b-8c35-f78fc9e7d101
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	58ae89ef-437f-4450-99a5-e05840b03db6
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	c10f4b8b-5dde-4961-8540-dd194ae8ee99
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	556db563-15fe-48d2-acf9-326df71ee669
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	c71044ea-9ea4-4fc9-9c8c-cb5a1e036366
2e02981f-ea08-431d-b154-525ac1730aba	b9663630-209d-4385-b90c-c5c2eda7ad92
2e02981f-ea08-431d-b154-525ac1730aba	a617d881-0c88-4fa3-9374-492a407bebdd
2e02981f-ea08-431d-b154-525ac1730aba	f9494a84-1259-4fb4-aa3a-6247c9271915
2e02981f-ea08-431d-b154-525ac1730aba	7269b34a-aab5-4c99-bc87-6444ab9ffee0
2e02981f-ea08-431d-b154-525ac1730aba	0154f98c-e03f-46e8-a129-49d71870562c
2e02981f-ea08-431d-b154-525ac1730aba	7ced697a-5488-40ab-810a-216a72ffa556
2e02981f-ea08-431d-b154-525ac1730aba	2fcfa18c-c217-45e4-9c0e-ff3f5a68afb7
2e02981f-ea08-431d-b154-525ac1730aba	e32edeb4-b386-457b-b2b5-fb935e437a71
2e02981f-ea08-431d-b154-525ac1730aba	960d880a-ae58-4225-aac0-f35abb74eb4e
2e02981f-ea08-431d-b154-525ac1730aba	dad7ffe5-7f7b-4e20-9583-379423ca4d8d
2e02981f-ea08-431d-b154-525ac1730aba	cbca3d32-cc4c-497c-a42b-f7084605ef85
2e02981f-ea08-431d-b154-525ac1730aba	f006405d-4845-4300-8e9f-2247efcfccc8
2e02981f-ea08-431d-b154-525ac1730aba	c1d0a960-e4e5-4a14-8654-36cefbf12ae5
2e02981f-ea08-431d-b154-525ac1730aba	2936cce0-2120-4229-8a51-7c80c357309f
2e02981f-ea08-431d-b154-525ac1730aba	d04f7dc7-5def-4e6b-8c35-f78fc9e7d101
2e02981f-ea08-431d-b154-525ac1730aba	380e077e-aed6-4975-94c0-96ee813401d2
2e02981f-ea08-431d-b154-525ac1730aba	58ae89ef-437f-4450-99a5-e05840b03db6
2e02981f-ea08-431d-b154-525ac1730aba	613337b8-35c6-4bf9-b3a4-125e704047f3
2e02981f-ea08-431d-b154-525ac1730aba	e7e6e117-7516-42e7-b878-5ec53cbabcbb
2e02981f-ea08-431d-b154-525ac1730aba	c10f4b8b-5dde-4961-8540-dd194ae8ee99
2e02981f-ea08-431d-b154-525ac1730aba	556db563-15fe-48d2-acf9-326df71ee669
2e02981f-ea08-431d-b154-525ac1730aba	c71044ea-9ea4-4fc9-9c8c-cb5a1e036366
2e02981f-ea08-431d-b154-525ac1730aba	fee169b8-4a8f-4194-a0d1-ae5dba696003
2e02981f-ea08-431d-b154-525ac1730aba	b12fbc10-976b-4238-b553-d1133ac19472
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	f724ad5a-759c-49a9-ad2b-7ed395421558
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	b0e2618e-6f82-41e6-afa4-126e3f674646
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	c17b131a-c21b-4299-8974-eca0509f689f
2e02981f-ea08-431d-b154-525ac1730aba	004b2f72-5a84-44d9-b4cd-f0ac3f4b1067
2e02981f-ea08-431d-b154-525ac1730aba	f724ad5a-759c-49a9-ad2b-7ed395421558
2e02981f-ea08-431d-b154-525ac1730aba	b0e2618e-6f82-41e6-afa4-126e3f674646
2e02981f-ea08-431d-b154-525ac1730aba	b2adffb2-fd73-4c20-8e51-0fc291b0adda
2e02981f-ea08-431d-b154-525ac1730aba	1930c1a6-2cf9-4e15-8cc0-00737a02a2e1
2e02981f-ea08-431d-b154-525ac1730aba	c17b131a-c21b-4299-8974-eca0509f689f
2e02981f-ea08-431d-b154-525ac1730aba	b7d33eb6-eb8b-4174-a853-9a829f8e4157
2e02981f-ea08-431d-b154-525ac1730aba	adc668ef-f961-4dac-8128-a3190d5bdd96
2e02981f-ea08-431d-b154-525ac1730aba	38b90140-4da2-4569-9e0b-fd20da7bf8aa
2e02981f-ea08-431d-b154-525ac1730aba	1f81372f-f28c-4f9a-9c36-a480696d4530
2e02981f-ea08-431d-b154-525ac1730aba	546ac530-c25c-4739-8a01-b3fd5f99e057
2e02981f-ea08-431d-b154-525ac1730aba	589bf6b8-158c-439e-b9c8-62d65cd8a1a9
d2184a82-f206-40f8-9ebf-172c6ec8a669	94f2af0f-0331-4903-92a8-b36f2270bedf
3d11028b-8857-42b7-b96a-c557822ce9ab	b7d33eb6-eb8b-4174-a853-9a829f8e4157
3d11028b-8857-42b7-b96a-c557822ce9ab	adc668ef-f961-4dac-8128-a3190d5bdd96
3d11028b-8857-42b7-b96a-c557822ce9ab	38b90140-4da2-4569-9e0b-fd20da7bf8aa
3d11028b-8857-42b7-b96a-c557822ce9ab	1f81372f-f28c-4f9a-9c36-a480696d4530
3d11028b-8857-42b7-b96a-c557822ce9ab	94f2af0f-0331-4903-92a8-b36f2270bedf
2e02981f-ea08-431d-b154-525ac1730aba	94f2af0f-0331-4903-92a8-b36f2270bedf
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.roles (id, name, description, created_at) FROM stdin;
2e02981f-ea08-431d-b154-525ac1730aba	super_admin	Full system owner	2026-06-30 06:06:41.650474+03
dc91a10e-5ed0-4293-a4c1-5203eb8afbad	admin	Platform administrator	2026-07-03 14:28:57.572191+03
d2184a82-f206-40f8-9ebf-172c6ec8a669	customer	customer role	2026-07-03 15:59:21.462741+03
3d11028b-8857-42b7-b96a-c557822ce9ab	seller	seller role	2026-07-03 15:59:21.469109+03
\.


--
-- Data for Name: seller_business_categories; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.seller_business_categories (id, seller_id, category_id, created_at) FROM stdin;
\.


--
-- Data for Name: seller_kyc_documents; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.seller_kyc_documents (id, seller_id, document_type, document_url, status, rejection_reason, uploaded_at) FROM stdin;
\.


--
-- Data for Name: seller_payout_accounts; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.seller_payout_accounts (id, seller_id, account_type, provider, account_name, account_number, currency, is_default, created_at) FROM stdin;
\.


--
-- Data for Name: seller_profiles; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.seller_profiles (id, seller_id, business_description, business_country, business_region, business_city, business_address, product_description, years_in_business, website_url, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: sellers; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.sellers (id, user_id, business_name, business_category, contact_email, contact_phone, status, agreement_accepted, approved_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.sessions (id, user_id, refresh_token, expires_at, created_at) FROM stdin;
fdd6e4d1-4ac6-4258-9dad-4231974dd76a	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODMyNDg1MjIsInR5cGUiOiJyZWZyZXNoIn0.UpCzdl_JQbJ8B5aFt7vVqU4aDQAVb78gln-zjd7cl5Q	2026-07-05 13:48:42.591629+03	2026-06-28 13:48:42.125794+03
90bf6a02-b96c-4616-8130-1da045da9bcc	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODMzOTMwMTUsInR5cGUiOiJyZWZyZXNoIn0.WL1NoPoDVT01omcdzUfAocFS3VrjerXx84gEtsg0j6s	2026-07-07 05:56:55.834533+03	2026-06-30 05:56:55.343196+03
11ae849b-ead4-44f6-946c-4a79d2887496	d9f34501-1509-4be3-a592-2498585ec063	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkOWYzNDUwMS0xNTA5LTRiZTMtYTU5Mi0yNDk4NTg1ZWMwNjMiLCJleHAiOjE3ODMzOTM2NTMsInR5cGUiOiJyZWZyZXNoIn0.aL6lPREGYXNKNZIej4XMSwGFgcsN1ZCcqF-e91LgtUI	2026-07-07 06:07:33.236615+03	2026-06-30 06:07:32.764759+03
183a3c14-05d5-4566-a7e0-79ca750ae6ce	d9f34501-1509-4be3-a592-2498585ec063	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkOWYzNDUwMS0xNTA5LTRiZTMtYTU5Mi0yNDk4NTg1ZWMwNjMiLCJleHAiOjE3ODMzOTUxNDQsInR5cGUiOiJyZWZyZXNoIn0.uST1uTC2usmtzOebeCl2y4Q_kQQvaIYd2cHteSmmT1I	2026-07-07 06:32:24.441227+03	2026-06-30 06:32:23.775377+03
89039eb5-ef2b-4490-936e-7305d207557d	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODMzOTUzNjksInR5cGUiOiJyZWZyZXNoIn0.XIwvXMebnAP1v7B_Tyqe9ghwuDv5WTb-LPz5-toLQcs	2026-07-07 06:36:09.584402+03	2026-06-30 06:36:08.704869+03
2b4a2063-3e49-4741-b9c2-25bb56749bcc	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzM2NzksInR5cGUiOiJyZWZyZXNoIn0.0Wuj9QjiygS7XoP5baRDxOxuwiDPPklHbAXUEw1fbmY	2026-07-10 11:54:39.919324+03	2026-07-03 11:54:39.405005+03
5491db36-40cc-4b3a-81eb-e5d31a25af84	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzM3MTQsInR5cGUiOiJyZWZyZXNoIn0.IHJKC-WK6Q6YaHH8iLiBdFRVZWPFMt4YNVmKRKm2AwA	2026-07-10 11:55:14.504548+03	2026-07-03 11:55:13.985248+03
81f36bfb-663e-48f3-8134-42c18d14ab46	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzM3MTgsInR5cGUiOiJyZWZyZXNoIn0.MYMvobKsKV0J2eXj5TtDUTK84eBpK1PqaFWo1TvDRZA	2026-07-10 11:55:18.264286+03	2026-07-03 11:55:17.744964+03
932219a9-600e-4e40-bcce-f35174513720	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzM3MjMsInR5cGUiOiJyZWZyZXNoIn0.3ivYM1pJYh32BygAog_yFIkC5nwFigcucNG2DCVx9_A	2026-07-10 11:55:23.837233+03	2026-07-03 11:55:23.334129+03
8d5da6fe-2eda-44f1-90c3-fcc2af3d1079	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzM3MjYsInR5cGUiOiJyZWZyZXNoIn0.JHlRRqGGPMmK64zIoAJigZyZzg4ycTvMM0EBdl94YQc	2026-07-10 11:55:26.296215+03	2026-07-03 11:55:25.82697+03
e98826f6-3000-4b37-8e3b-74c6e53d6779	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxNDEsInR5cGUiOiJyZWZyZXNoIn0.gzMIg2PoKJZxuBjUKwGBzk7PGZ-1-buLtSQwbLLI2YM	2026-07-10 12:02:21.284054+03	2026-07-03 12:02:20.770312+03
7d25af23-48c9-4d8f-80d2-6bcd07c2a057	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxNTEsInR5cGUiOiJyZWZyZXNoIn0.gUMzP7v8Xrcp51ksLYR5olLG7lOUoWWZmkf1M8ykB9o	2026-07-10 12:02:31.12224+03	2026-07-03 12:02:30.605492+03
d1c50c2f-59e7-4acc-b7c0-cdbefad30283	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxNTIsInR5cGUiOiJyZWZyZXNoIn0.kGc4zkfT3dvC7iEErXsOxZd7iBq9ISvOal6AObB8DHY	2026-07-10 12:02:32.028122+03	2026-07-03 12:02:31.338214+03
bc8ecd3b-e2f8-4e41-9565-bd5cdec969d9	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxNTMsInR5cGUiOiJyZWZyZXNoIn0.oO2OBPN2vN1X4LgzwJtiPOf9XnDY7e6L3Q17lnFyG0M	2026-07-10 12:02:33.500819+03	2026-07-03 12:02:32.962227+03
ff55a59c-0dbe-4517-b23e-accaebe92c3a	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxNTYsInR5cGUiOiJyZWZyZXNoIn0.530FWHwu7y2xJhW80NkA3bpg0bY2DiYyq2rP7LRMqCA	2026-07-10 12:02:36.651532+03	2026-07-03 12:02:36.118145+03
70366dab-afe0-4cc7-a733-893b3ea986a5	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxNjMsInR5cGUiOiJyZWZyZXNoIn0.W-0Jjd-QO6d1885FC61wTxT_EV3MRL9935PwlAeqZLY	2026-07-10 12:02:43.15947+03	2026-07-03 12:02:42.620619+03
eafbab37-4170-4f13-aabb-8a5087eecf40	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxNjYsInR5cGUiOiJyZWZyZXNoIn0.Itz_WUo647Q1rWsiONPXYtkp0jtR3ng7ai_ULcdcRkw	2026-07-10 12:02:46.346223+03	2026-07-03 12:02:45.891449+03
e1c0de19-f6fd-44f2-a927-1d84d3f56617	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxNzQsInR5cGUiOiJyZWZyZXNoIn0.0cq0W-uMQYMZli0j5VK-3_gLjv9_q5whaVTdDWlPYxo	2026-07-10 12:02:54.320081+03	2026-07-03 12:02:53.768299+03
449a312e-95cd-45f5-8100-167259ac784b	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQxOTUsInR5cGUiOiJyZWZyZXNoIn0.aQGEETmtnj8OyeSnfO5eUWsDm9PndbUdtI0BuibjJJw	2026-07-10 12:03:15.41048+03	2026-07-03 12:03:14.967495+03
4bc96e14-1a9b-46e2-b2e0-e3f148bf0321	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQ0NzcsInR5cGUiOiJyZWZyZXNoIn0.P5zyOuSiXyA4TS3wPK3wy-GR2e8jAZqBYrsRpxv9QOM	2026-07-10 12:07:57.401343+03	2026-07-03 12:07:56.79628+03
afaf4a41-21f2-4cef-8b16-75307b7bb843	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzQ5MDEsInR5cGUiOiJyZWZyZXNoIn0.cSpZxfL7MYL4G3R3-So4FejeR1ErHc4fagkH7xFpknQ	2026-07-10 12:15:01.845941+03	2026-07-03 12:15:00.962656+03
bb4647ec-7daf-416b-96e6-9f306f59d653	d9f34501-1509-4be3-a592-2498585ec063	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkOWYzNDUwMS0xNTA5LTRiZTMtYTU5Mi0yNDk4NTg1ZWMwNjMiLCJleHAiOjE3ODM2NzU1NjMsInR5cGUiOiJyZWZyZXNoIn0.W0OatLmCJbOCBVkvj86My6bGkYtN7R5uJ654YJwVrTo	2026-07-10 12:26:03.905153+03	2026-07-03 12:26:03.131309+03
cd6f3300-5b64-431c-9a85-6e0b3d7ac91b	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM2NzcxNjAsInR5cGUiOiJyZWZyZXNoIn0.ttXZjSpFzf0_7-iWVKQj-FNDWjNsNj02darwny0DuH4	2026-07-10 12:52:40.023852+03	2026-07-03 12:52:39.212681+03
d1543ded-2fc4-48b2-bbd5-f6961630a1e9	d9f34501-1509-4be3-a592-2498585ec063	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkOWYzNDUwMS0xNTA5LTRiZTMtYTU5Mi0yNDk4NTg1ZWMwNjMiLCJleHAiOjE3ODM2ODM2MzEsInR5cGUiOiJyZWZyZXNoIn0.LnYWSy2aYYUHrRm4-U2s69EGYTQwhsVKv2gshxMkXzE	2026-07-10 14:40:31.541988+03	2026-07-03 14:40:30.858926+03
dec01e07-caa3-443c-bdab-ae1e476af327	d9f34501-1509-4be3-a592-2498585ec063	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkOWYzNDUwMS0xNTA5LTRiZTMtYTU5Mi0yNDk4NTg1ZWMwNjMiLCJleHAiOjE3ODM2ODg0NTIsInR5cGUiOiJyZWZyZXNoIn0.i_2EUgH4avUKh-R3Kz9qxj80g1w7e68tn4blllnFKhg	2026-07-10 16:00:52.923041+03	2026-07-03 16:00:52.281229+03
4bc586ff-f85c-44a5-ab87-17c6fc01624e	d9f34501-1509-4be3-a592-2498585ec063	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkOWYzNDUwMS0xNTA5LTRiZTMtYTU5Mi0yNDk4NTg1ZWMwNjMiLCJleHAiOjE3ODM2ODg4MTMsInR5cGUiOiJyZWZyZXNoIn0.WTPPU7nEXqUSSVLyhZSbFXBCRI6i8RNIEnJp6I4-StM	2026-07-10 16:06:53.002751+03	2026-07-03 16:06:52.145983+03
11491384-7ff6-4fd1-ab28-a7b7636f93fe	d9f34501-1509-4be3-a592-2498585ec063	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkOWYzNDUwMS0xNTA5LTRiZTMtYTU5Mi0yNDk4NTg1ZWMwNjMiLCJleHAiOjE3ODM2OTA0ODksInR5cGUiOiJyZWZyZXNoIn0.-7CT7NwiEGhAuou_SQOVon6FUS50Dr8vzXpvPuLLqno	2026-07-10 16:34:49.484007+03	2026-07-03 16:34:48.504853+03
77a3175c-2cfb-41f4-a8aa-ee6045cc20d2	d9f34501-1509-4be3-a592-2498585ec063	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkOWYzNDUwMS0xNTA5LTRiZTMtYTU5Mi0yNDk4NTg1ZWMwNjMiLCJleHAiOjE3ODM2OTA2MjYsInR5cGUiOiJyZWZyZXNoIn0._9_HD4HB4Ksd90NX_FbDfQuzCMW07EnbrSt1TtgXBm8	2026-07-10 16:37:06.029954+03	2026-07-03 16:37:05.231961+03
9dda9a72-5a4f-4f6c-8e78-9f44ae393ebc	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM3NTQ0ODQsInR5cGUiOiJyZWZyZXNoIn0.LxOhqzq0_RUKyALSrOL2vc1HekvMfUPbFFg08OadStI	2026-07-11 10:21:24.736857+03	2026-07-04 10:21:24.208759+03
90c486d9-0771-4eb6-b54d-ee855c837ebb	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODM3NzczNjAsInR5cGUiOiJyZWZyZXNoIn0.pmOTqgG7iR-Kb1RcNdYLQ7h0SxMS_hvxtMOWNmK533A	2026-07-11 16:42:40.472945+03	2026-07-04 16:42:39.97997+03
36c8a727-61bc-40fb-aa38-99acfb3bbc33	08823972-8709-402a-8227-971e755526e5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwODgyMzk3Mi04NzA5LTQwMmEtODIyNy05NzFlNzU1NTI2ZTUiLCJleHAiOjE3ODQ3MjI5NzcsInR5cGUiOiJyZWZyZXNoIn0.9Xa0PDObVntqvGPxIamk_FcOWOayasBg5OtRSeN4E-E	2026-07-22 15:22:57.845077+03	2026-07-15 15:22:56.766643+03
\.


--
-- Data for Name: store_gallery_images; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.store_gallery_images (id, store_id, image_url, caption, display_order, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: store_opening_hours; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.store_opening_hours (id, store_id, day_of_week, day_number, open_time, close_time, is_closed, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: stores; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.stores (id, seller_id, store_name, slug, description, logo_url, banner_url, contact_email, contact_phone, website_url, country, region, district, ward, street, latitude, longitude, opening_time, closing_time, shipping_policy, return_policy, privacy_policy, facebook_url, instagram_url, twitter_url, tiktok_url, youtube_url, status, is_verified, is_featured, rating, review_count, followers_count, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_permissions; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.user_permissions (user_id, permission_id) FROM stdin;
\.


--
-- Data for Name: user_roles; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.user_roles (user_id, role_id) FROM stdin;
d9f34501-1509-4be3-a592-2498585ec063	2e02981f-ea08-431d-b154-525ac1730aba
08823972-8709-402a-8227-971e755526e5	dc91a10e-5ed0-4293-a4c1-5203eb8afbad
6ea435b0-a945-45bd-ab29-fce4af3e29e3	dc91a10e-5ed0-4293-a4c1-5203eb8afbad
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.users (id, first_name, last_name, email, phone, password_hash, status, is_verified, last_login_at, created_at, updated_at) FROM stdin;
189d5f98-ec3f-4a87-91e5-0503d0c298d9	Katani	Ndiye	mashakakatani16@gmail.com	+255635673730	$2b$12$TVfnyiJ5UxXsNTr1o9QEdOZ4e7GjRyTAjyD.YTEYphjtLgrs6gYPG	pending_verification	f	\N	2026-06-28 15:18:27.626971+03	\N
1e46cf5a-35f7-4892-bcd4-06e3007ef1e9	Katani	Ndiye	mashakakatani6@gmail.com	+255635673750	$2b$12$0f5dibmTn3X7Cr4xnZjcau/JIHD0EWGrUqNXKyT2w/QMFbBNnFtWi	pending_verification	f	\N	2026-06-28 15:23:04.78371+03	\N
c2494096-838e-4a5f-9e53-928ce92cba4b	Katani	Ndiye	mashakakata6@gmail.com	+255635673740	$2b$12$sU3TXRgUIXjrz8uSonR/hehTGkFVUbIyqnnJGbWh4Jk98hGUpUCl2	pending_verification	f	\N	2026-06-28 15:26:47.547031+03	\N
d208edeb-ebd8-4b9e-842d-12de37498c15	Katani	Ndiye	mashakakaerta6@gmail.com	+255635673732	$2b$12$oWlRR2Hrmko7ILgZhXLGuOO0OM0hVhYlhXfSzGFlAcvkkKJwcy7ZO	pending_verification	f	\N	2026-06-28 15:30:03.760047+03	\N
54aa6291-1df5-4d9e-8c17-78d7082f58a4	Katani	Ndiye	haminaomary0@gmail.com	+255624909756	$2b$12$UUFqVz2S9msfL6Kw.gIzmOERtrB.ZTd/VqFdUORym.0NrFPoDd7yO	pending_verification	f	\N	2026-06-28 15:33:49.957187+03	\N
5d979c0c-f753-4471-944c-b4ff94f00af5	Katani	Ndiye	haminaomar23@gmail.com	+255682303730	$2b$12$zXSFWOfnplTbs/.dljQLzufFktDxvbKZ2tjWlYgBVyRNqUbVzWQre	pending_verification	f	\N	2026-06-28 15:35:13.248574+03	\N
68f19246-216b-4162-af0c-968cb58c714a	Katani	Ndiye	haminaomfxtrxc@gmail.com	+255613976254	$2b$12$SFGX44M83/6xlzAbk1Ggl.AMogXkBOwBNra1yVMKX2C4s/Zb6Evwi	pending_verification	f	\N	2026-06-28 15:39:24.354269+03	\N
979ed518-5054-4cc5-9582-05c68b51631b	Katani	Ndiye	adamtesting34@gmail.com	+255767939800	$2b$12$DDuzjQ1QisykWMLvAR2cEeFpThDbTaJ6VlHShnS0uvTIN57xSZEGK	pending_verification	f	\N	2026-06-29 15:43:34.98384+03	\N
6ea435b0-a945-45bd-ab29-fce4af3e29e3	Adam	Katani	switcherbaba76@gmail.com	+255767939809	$2b$12$YtkQyzHebsUesVVBslcUueUEYKaaHQXYX8gnlTYhJbh6tfCd.7ElG	active	t	2026-07-03 14:39:59.662091+03	2026-06-27 20:30:33.00389+03	2026-07-03 14:39:58.91313+03
d9f34501-1509-4be3-a592-2498585ec063	Super	Admin	superadmin@xerin.com	255767939809	$2b$12$XyTS2GGvtxCgbOOlEpe.q.ObhbBDmj2FZIslaV2tsjOb14lVu2AHW	active	t	2026-07-03 16:37:06.030103+03	2026-06-30 06:06:41.143018+03	2026-07-03 16:37:05.231961+03
08823972-8709-402a-8227-971e755526e5	ADAM	KATANI	mashakaadam123@gmail.com	+255694021848	$2b$12$Eg5M6i3l4oEGCcFFXbjvWeU9RfQCN4FWUt4et9hbn.Z34UPrAkbRK	active	t	2026-07-15 15:22:57.846193+03	2026-06-28 13:47:39.215527+03	2026-07-15 15:22:56.766643+03
\.


--
-- Name: addresses addresses_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: brands brands_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_pkey PRIMARY KEY (id);


--
-- Name: business_categories business_categories_name_key; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.business_categories
    ADD CONSTRAINT business_categories_name_key UNIQUE (name);


--
-- Name: business_categories business_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.business_categories
    ADD CONSTRAINT business_categories_pkey PRIMARY KEY (id);


--
-- Name: business_categories business_categories_slug_key; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.business_categories
    ADD CONSTRAINT business_categories_slug_key UNIQUE (slug);


--
-- Name: cart_items cart_items_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.cart_items
    ADD CONSTRAINT cart_items_pkey PRIMARY KEY (id);


--
-- Name: carts carts_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.carts
    ADD CONSTRAINT carts_pkey PRIMARY KEY (id);


--
-- Name: carts carts_user_id_key; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.carts
    ADD CONSTRAINT carts_user_id_key UNIQUE (user_id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: coupons coupons_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.coupons
    ADD CONSTRAINT coupons_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_variant_id_key; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_variant_id_key UNIQUE (variant_id);


--
-- Name: order_items order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_pkey PRIMARY KEY (id);


--
-- Name: order_status_history order_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.order_status_history
    ADD CONSTRAINT order_status_history_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: otp_requests otp_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.otp_requests
    ADD CONSTRAINT otp_requests_pkey PRIMARY KEY (id);


--
-- Name: payment_transactions payment_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_pkey PRIMARY KEY (id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_code_key; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_code_key UNIQUE (code);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: product_images product_images_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.product_images
    ADD CONSTRAINT product_images_pkey PRIMARY KEY (id);


--
-- Name: product_tags product_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.product_tags
    ADD CONSTRAINT product_tags_pkey PRIMARY KEY (id);


--
-- Name: product_variants product_variants_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.product_variants
    ADD CONSTRAINT product_variants_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_id);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: seller_business_categories seller_business_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_business_categories
    ADD CONSTRAINT seller_business_categories_pkey PRIMARY KEY (id);


--
-- Name: seller_kyc_documents seller_kyc_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_kyc_documents
    ADD CONSTRAINT seller_kyc_documents_pkey PRIMARY KEY (id);


--
-- Name: seller_payout_accounts seller_payout_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_payout_accounts
    ADD CONSTRAINT seller_payout_accounts_pkey PRIMARY KEY (id);


--
-- Name: seller_profiles seller_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_profiles
    ADD CONSTRAINT seller_profiles_pkey PRIMARY KEY (id);


--
-- Name: seller_profiles seller_profiles_seller_id_key; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_profiles
    ADD CONSTRAINT seller_profiles_seller_id_key UNIQUE (seller_id);


--
-- Name: sellers sellers_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.sellers
    ADD CONSTRAINT sellers_pkey PRIMARY KEY (id);


--
-- Name: sellers sellers_user_id_key; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.sellers
    ADD CONSTRAINT sellers_user_id_key UNIQUE (user_id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: store_gallery_images store_gallery_images_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.store_gallery_images
    ADD CONSTRAINT store_gallery_images_pkey PRIMARY KEY (id);


--
-- Name: store_opening_hours store_opening_hours_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.store_opening_hours
    ADD CONSTRAINT store_opening_hours_pkey PRIMARY KEY (id);


--
-- Name: stores stores_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.stores
    ADD CONSTRAINT stores_pkey PRIMARY KEY (id);


--
-- Name: store_opening_hours uq_store_opening_hours_store_day; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.store_opening_hours
    ADD CONSTRAINT uq_store_opening_hours_store_day UNIQUE (store_id, day_of_week);


--
-- Name: user_permissions user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_pkey PRIMARY KEY (user_id, permission_id);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_brands_slug; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_brands_slug ON public.brands USING btree (slug);


--
-- Name: ix_categories_slug; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_categories_slug ON public.categories USING btree (slug);


--
-- Name: ix_coupons_code; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_coupons_code ON public.coupons USING btree (code);


--
-- Name: ix_product_tags_tag; Type: INDEX; Schema: public; Owner: app_user
--

CREATE INDEX ix_product_tags_tag ON public.product_tags USING btree (tag);


--
-- Name: ix_product_variants_sku; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_product_variants_sku ON public.product_variants USING btree (sku);


--
-- Name: ix_products_sku; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_products_sku ON public.products USING btree (sku);


--
-- Name: ix_products_slug; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_products_slug ON public.products USING btree (slug);


--
-- Name: ix_store_gallery_images_store_id; Type: INDEX; Schema: public; Owner: app_user
--

CREATE INDEX ix_store_gallery_images_store_id ON public.store_gallery_images USING btree (store_id);


--
-- Name: ix_store_opening_hours_store_id; Type: INDEX; Schema: public; Owner: app_user
--

CREATE INDEX ix_store_opening_hours_store_id ON public.store_opening_hours USING btree (store_id);


--
-- Name: ix_stores_seller_id; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_stores_seller_id ON public.stores USING btree (seller_id);


--
-- Name: ix_stores_slug; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_stores_slug ON public.stores USING btree (slug);


--
-- Name: ix_stores_status; Type: INDEX; Schema: public; Owner: app_user
--

CREATE INDEX ix_stores_status ON public.stores USING btree (status);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_phone; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_users_phone ON public.users USING btree (phone);


--
-- Name: addresses addresses_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: cart_items cart_items_cart_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.cart_items
    ADD CONSTRAINT cart_items_cart_id_fkey FOREIGN KEY (cart_id) REFERENCES public.carts(id);


--
-- Name: cart_items cart_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.cart_items
    ADD CONSTRAINT cart_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: cart_items cart_items_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.cart_items
    ADD CONSTRAINT cart_items_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.product_variants(id);


--
-- Name: carts carts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.carts
    ADD CONSTRAINT carts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: categories categories_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.categories(id);


--
-- Name: coupons coupons_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.coupons
    ADD CONSTRAINT coupons_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.users(id);


--
-- Name: inventory inventory_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: inventory inventory_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public.users(id);


--
-- Name: inventory inventory_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.product_variants(id);


--
-- Name: order_items order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: order_items order_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: order_items order_items_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.sellers(id);


--
-- Name: order_items order_items_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.product_variants(id);


--
-- Name: order_status_history order_status_history_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.order_status_history
    ADD CONSTRAINT order_status_history_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.users(id);


--
-- Name: order_status_history order_status_history_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.order_status_history
    ADD CONSTRAINT order_status_history_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: orders orders_shipping_address_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_shipping_address_id_fkey FOREIGN KEY (shipping_address_id) REFERENCES public.addresses(id);


--
-- Name: orders orders_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: otp_requests otp_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.otp_requests
    ADD CONSTRAINT otp_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: payment_transactions payment_transactions_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id);


--
-- Name: payments payments_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: payments payments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: product_images product_images_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.product_images
    ADD CONSTRAINT product_images_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: product_tags product_tags_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.product_tags
    ADD CONSTRAINT product_tags_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: product_variants product_variants_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.product_variants
    ADD CONSTRAINT product_variants_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: products products_brand_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_brand_id_fkey FOREIGN KEY (brand_id) REFERENCES public.brands(id);


--
-- Name: products products_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: products products_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.sellers(id);


--
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id);


--
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: seller_business_categories seller_business_categories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_business_categories
    ADD CONSTRAINT seller_business_categories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: seller_business_categories seller_business_categories_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_business_categories
    ADD CONSTRAINT seller_business_categories_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.sellers(id);


--
-- Name: seller_kyc_documents seller_kyc_documents_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_kyc_documents
    ADD CONSTRAINT seller_kyc_documents_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.sellers(id);


--
-- Name: seller_payout_accounts seller_payout_accounts_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_payout_accounts
    ADD CONSTRAINT seller_payout_accounts_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.sellers(id);


--
-- Name: seller_profiles seller_profiles_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.seller_profiles
    ADD CONSTRAINT seller_profiles_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.sellers(id);


--
-- Name: sellers sellers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.sellers
    ADD CONSTRAINT sellers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: store_gallery_images store_gallery_images_store_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.store_gallery_images
    ADD CONSTRAINT store_gallery_images_store_id_fkey FOREIGN KEY (store_id) REFERENCES public.stores(id) ON DELETE CASCADE;


--
-- Name: store_opening_hours store_opening_hours_store_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.store_opening_hours
    ADD CONSTRAINT store_opening_hours_store_id_fkey FOREIGN KEY (store_id) REFERENCES public.stores(id) ON DELETE CASCADE;


--
-- Name: stores stores_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.stores
    ADD CONSTRAINT stores_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.sellers(id) ON DELETE CASCADE;


--
-- Name: user_permissions user_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id);


--
-- Name: user_permissions user_permissions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_roles user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

GRANT ALL ON SCHEMA public TO app_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO postgres;


--
-- PostgreSQL database dump complete
--

\unrestrict ForGPR5Us4D0r1sfSbniZHBohHqliuyqgHCfJKVvdbBc7h5LRkYuKfGddihoaaI

