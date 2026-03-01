-- Migration: Add AI reasoning columns to approval queue
-- Date: 2026-03-01
-- Description: Store LLM agent reasoning for cost estimation and validation

-- Add AI reasoning columns
ALTER TABLE approval_queue ADD COLUMN ai_cost_reasoning TEXT;
ALTER TABLE approval_queue ADD COLUMN ai_validation_reasoning TEXT;
