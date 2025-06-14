--
-- PostgreSQL database dump
--

-- Dumped from database version 16.8
-- Dumped by pg_dump version 16.8

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin_forgot_password; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admin_forgot_password (
    id integer NOT NULL,
    expire_after timestamp with time zone DEFAULT (now() + '00:30:00'::interval),
    token character varying(32),
    user_id integer NOT NULL
);


ALTER TABLE public.admin_forgot_password owner to idportal;

--
-- Name: admin_forgot_password_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admin_forgot_password_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admin_forgot_password_id_seq owner to idportal;

--
-- Name: admin_forgot_password_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admin_forgot_password_id_seq OWNED BY public.admin_forgot_password.id;


--
-- Name: admins; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admins (
    id integer NOT NULL,
    first_name text,
    last_name text,
    username character varying(20),
    password text,
    email text,
    status integer DEFAULT 1,
    on_login integer DEFAULT 1,
    role character varying(8)
);


ALTER TABLE public.admins owner to idportal;

--
-- Name: admins_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admins_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admins_id_seq owner to idportal;

--
-- Name: admins_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admins_id_seq OWNED BY public.admins.id;


--
-- Name: bfa; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bfa (
    id integer NOT NULL,
    email text,
    ip_address inet,
    failed_attempts integer DEFAULT 1,
    timestamp_inserted timestamp without time zone DEFAULT now()
);


ALTER TABLE public.bfa owner to idportal;

--
-- Name: bfa_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bfa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bfa_id_seq owner to idportal;

--
-- Name: bfa_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bfa_id_seq OWNED BY public.bfa.id;


--
-- Name: submissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.submissions (
    request_id integer NOT NULL,
    first_name text,
    last_name text,
    id_number text,
    location character varying(15),
    timestamp_inserted timestamp with time zone DEFAULT now(),
    status character varying(1) DEFAULT 'N'::character varying,
    ip_address inet,
    photo_filepath text,
    license_filepath text,
    comments character varying(250),
    email text
);


ALTER TABLE public.submissions owner to idportal;

--
-- Name: submissions_request_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.submissions_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.submissions_request_id_seq owner to idportal;

--
-- Name: submissions_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.submissions_request_id_seq OWNED BY public.submissions.request_id;


--
-- Name: admin_forgot_password id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_forgot_password ALTER COLUMN id SET DEFAULT nextval('public.admin_forgot_password_id_seq'::regclass);


--
-- Name: admins id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins ALTER COLUMN id SET DEFAULT nextval('public.admins_id_seq'::regclass);


--
-- Name: bfa id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bfa ALTER COLUMN id SET DEFAULT nextval('public.bfa_id_seq'::regclass);


--
-- Name: submissions request_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submissions ALTER COLUMN request_id SET DEFAULT nextval('public.submissions_request_id_seq'::regclass);


--
-- Name: admin_forgot_password admin_forgot_password_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_forgot_password
    ADD CONSTRAINT admin_forgot_password_pkey PRIMARY KEY (id);


--
-- Name: admins admins_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_email_key UNIQUE (email);


--
-- Name: admins admins_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_pkey PRIMARY KEY (id);


--
-- Name: admins admins_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_username_key UNIQUE (username);


--
-- Name: bfa bfa_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bfa
    ADD CONSTRAINT bfa_email_key UNIQUE (email);


--
-- Name: bfa bfa_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bfa
    ADD CONSTRAINT bfa_pkey PRIMARY KEY (id);


--
-- Name: admins email_contraint; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT email_contraint UNIQUE (email);


--
-- Name: submissions submissions_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_email_key UNIQUE (email);


--
-- Name: submissions submissions_id_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_id_number_key UNIQUE (id_number);


--
-- Name: submissions submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_pkey PRIMARY KEY (request_id);


--
-- Name: admins username_contraint; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT username_contraint UNIQUE (username);


--
-- Name: admins_email_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX admins_email_idx ON public.admins USING btree (email);


--
-- Name: admins_id_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX admins_id_idx ON public.admins USING btree (id);


--
-- Name: admins_username_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX admins_username_idx ON public.admins USING btree (username);


--
-- Name: bfa_email_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX bfa_email_idx ON public.bfa USING btree (email);


--
-- Name: submissions_email_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX submissions_email_idx ON public.submissions USING btree (email);


--
-- Name: submissions_id_number_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX submissions_id_number_idx ON public.submissions USING btree (id_number);


--
-- Name: submissions_status_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX submissions_status_idx ON public.submissions USING btree (status);


--
-- Name: admin_forgot_password admin_forgot_password_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_forgot_password
    ADD CONSTRAINT admin_forgot_password_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.admins(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO idportal;


--
-- Name: TABLE admin_forgot_password; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.admin_forgot_password TO idportal;


--
-- Name: SEQUENCE admin_forgot_password_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT USAGE ON SEQUENCE public.admin_forgot_password_id_seq TO idportal;


--
-- Name: TABLE admins; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.admins TO idportal;


--
-- Name: SEQUENCE admins_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT USAGE ON SEQUENCE public.admins_id_seq TO idportal;


--
-- Name: TABLE bfa; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.bfa TO idportal;


--
-- Name: SEQUENCE bfa_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT USAGE ON SEQUENCE public.bfa_id_seq TO idportal;


--
-- Name: TABLE submissions; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.submissions TO idportal;


--
-- Name: SEQUENCE submissions_request_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT USAGE ON SEQUENCE public.submissions_request_id_seq TO idportal;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE idportal IN SCHEMA public GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO idportal;


--
-- PostgreSQL database dump complete
--
--
-- Add admin account
--
INSERT INTO public.admins (first_name, last_name, username, password, email, status, on_login, role) VALUES ('Admin', 'Account', 'admin', '$2b$12$RrvdG7OilbQVI7WJaNHMKOWzZfxgsuCAuwyA9XkwqKeoI1UeOiX9e', 'admin@email.com', 1, 0, 'super');

