-- Airline Loyalty SQL schema for MySQL 8.x
-- CSVs use \N for SQL NULL values.
-- Decimal types are used for money/financial metrics to avoid floating-point rounding.

CREATE DATABASE IF NOT EXISTS airline_loyalty
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE airline_loyalty;

DROP TABLE IF EXISTS customer_flight_activity;
DROP TABLE IF EXISTS airline_loyalty_data_dictionary;
DROP TABLE IF EXISTS calendar;
DROP TABLE IF EXISTS customer_loyalty_history;

CREATE TABLE customer_loyalty_history (
    loyalty_number BIGINT NOT NULL,
    country VARCHAR(100) NOT NULL,
    province VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    gender VARCHAR(20) NOT NULL,
    education VARCHAR(50) NOT NULL,
    salary DECIMAL(12,2) NOT NULL,
    marital_status VARCHAR(30) NOT NULL,
    loyalty_card VARCHAR(30) NOT NULL,
    clv DECIMAL(12,2) NOT NULL,
    enrollment_type VARCHAR(50) NOT NULL,
    enrollment_date DATE NOT NULL,
    cancellation_date DATE NULL,
    PRIMARY KEY (loyalty_number),
    CHECK (salary >= 0),
    CHECK (clv >= 0),
    CHECK (cancellation_date IS NULL OR cancellation_date >= enrollment_date)
) ENGINE=InnoDB;

CREATE TABLE calendar (
    date DATE NOT NULL,
    start_of_year DATE NOT NULL,
    start_of_quarter DATE NOT NULL,
    start_of_month DATE NOT NULL,
    PRIMARY KEY (date)
) ENGINE=InnoDB;

CREATE TABLE customer_flight_activity (
    loyalty_number BIGINT NOT NULL,
    activity_date DATE NOT NULL,
    total_flights INT NOT NULL,
    distance INT NOT NULL,
    points_accumulated DECIMAL(12,2) NOT NULL,
    points_redeemed INT NOT NULL,
    dollar_cost_points_redeemed DECIMAL(12,2) NOT NULL,
    PRIMARY KEY (loyalty_number, activity_date),
    CONSTRAINT fk_activity_loyalty
        FOREIGN KEY (loyalty_number)
        REFERENCES customer_loyalty_history (loyalty_number)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CHECK (total_flights >= 0),
    CHECK (distance >= 0),
    CHECK (points_accumulated >= 0),
    CHECK (points_redeemed >= 0),
    CHECK (dollar_cost_points_redeemed >= 0)
) ENGINE=InnoDB;

CREATE TABLE airline_loyalty_data_dictionary (
    table_name VARCHAR(100) NOT NULL,
    field VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    PRIMARY KEY (table_name, field)
) ENGINE=InnoDB;

-- Recommended import order:
-- 1. customer_loyalty_history_clean.csv
-- 2. calendar_clean.csv
-- 3. customer_flight_activity_clean.csv
-- 4. airline_loyalty_data_dictionary_clean.csv
--
-- Example LOAD DATA pattern (adjust LOCAL according to your MySQL Workbench setup):
--
-- LOAD DATA LOCAL INFILE 'customer_loyalty_history_clean.csv'
-- INTO TABLE customer_loyalty_history
-- FIELDS TERMINATED BY ',' ENCLOSED BY '"'
-- LINES TERMINATED BY '\n'
-- IGNORE 1 ROWS
-- (loyalty_number, country, province, city, postal_code, gender, education,
--  salary, marital_status, loyalty_card, clv, enrollment_type,
--  enrollment_date, cancellation_date);
--
-- Because the files use \N, MySQL LOAD DATA will interpret it as NULL by default.
