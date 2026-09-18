-- 1. Customer Demographics & Segmentation Analysis
-- Average Customer Lifetime Value (CLV) and Salary by Loyalty Card Tier
SELECT 
    loyalty_card,
    COUNT(loyalty_number) AS total_members,
    ROUND(AVG(clv), 2) AS avg_clv,
    ROUND(AVG(salary), 2) AS avg_salary,
    ROUND(MIN(salary), 2) AS min_salary,
    ROUND(MAX(salary), 2) AS max_salary
FROM customer_loyalty_history
GROUP BY loyalty_card
ORDER BY avg_clv DESC;

-- 2. Distribution of Loyalty Members by Province & Gender
SELECT 
    province,
    gender,
    COUNT(loyalty_number) AS member_count,
    ROUND(AVG(clv), 2) AS avg_clv
FROM customer_loyalty_history
GROUP BY province, gender
ORDER BY member_count DESC;

-- Flight Activity & Distance Patterns:
-- Flight Volume and Distance Traveled by Loyalty Card Status
SELECT 
    h.loyalty_card,
    SUM(f.total_flights) AS aggregate_flights,
    SUM(f.distance) AS total_distance_miles,
    ROUND(AVG(f.distance), 2) AS avg_distance_per_period
FROM customer_flight_activity f
JOIN customer_loyalty_history h 
    ON f.loyalty_number = h.loyalty_number
GROUP BY h.loyalty_card
ORDER BY total_distance_miles DESC;

-- Monthly Flight Trends Across Years
select * from customer_flight_activity;
SELECT 
    year(activity_date),
    month(activity_date),
    SUM(total_flights) AS total_flights_booked,
    SUM(distance) AS total_flight_distance
FROM customer_flight_activity
GROUP BY year(activity_date), month(activity_date)
ORDER BY year(activity_date) ASC, month(activity_date) ASC;

-- Points Earned vs. Points Redeemed Analysis: 
-- Point Accumulation vs. Redemption by Education Level:
SELECT 
    h.education,
    SUM(f.points_accumulated) AS total_points_earned,
    SUM(f.points_redeemed) AS total_points_redeemed,
    ROUND(SUM(f.dollar_cost_points_redeemed), 2) AS total_redemption_cost_usd,
    ROUND(SUM(f.points_redeemed) * 100.0 / NULLIF(SUM(f.points_accumulated), 0), 2) AS redemption_rate_pct
FROM customer_flight_activity f
JOIN customer_loyalty_history h 
    ON f.loyalty_number = h.loyalty_number
GROUP BY h.education
ORDER BY total_points_earned DESC;

-- Churn & Enrollment Dynamics:
-- Cancellation Rates by Enrollment Cohort Year:

select * from customer_loyalty_history;
SELECT 
    year(enrollment_date) as Enrollment_Cohort_Year,
    COUNT(loyalty_number) AS total_enrolled,
    COUNT(year(cancellation_date)) AS total_cancelled,
    ROUND(COUNT(year(cancellation_date)) * 100.0 / COUNT(loyalty_number), 2) AS churn_rate_pct
FROM customer_loyalty_history
GROUP BY year(enrollment_date)
ORDER BY year(enrollment_date) ASC;

-- Active vs. Churned Customer Flight Behavior Comparison:

SELECT 
    CASE 
        WHEN h.cancellation_date IS NOT NULL THEN 'Churned'
        ELSE 'Active'
    END AS member_status,
    COUNT(DISTINCT h.loyalty_number) AS member_count,
    ROUND(AVG(f.total_flights), 2) AS avg_monthly_flights,
    ROUND(AVG(f.points_accumulated), 2) AS avg_points_earned
FROM customer_loyalty_history h
LEFT JOIN customer_flight_activity f 
    ON h.loyalty_number = f.loyalty_number
GROUP BY member_status;

-- Top-Tier Member Identification (Window Functions)
-- Top 10 Members by Total Distance Traveled:
SELECT 
    h.loyalty_number,
    h.city,
    h.province,
    h.loyalty_card,
    h.clv,
    SUM(f.total_flights) AS total_flights,
    SUM(f.distance) AS total_distance
FROM customer_loyalty_history h
JOIN customer_flight_activity f 
    ON h.loyalty_number = f.loyalty_number
GROUP BY h.loyalty_number, h.city, h.province, h.loyalty_card, h.clv
ORDER BY total_distance DESC
LIMIT 10;



