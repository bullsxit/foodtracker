-- Run this once in Neon SQL Editor if the app was deployed before 2026-03
-- and you see: "value out of int32 range" for telegram_id (e.g. 7383463413).
-- Telegram user IDs can exceed INTEGER (2^31-1); this changes columns to BIGINT.

ALTER TABLE users           ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE weight_history  ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE foods           ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE daily_calories  ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE water_intake    ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE workouts        ALTER COLUMN telegram_id TYPE BIGINT;
