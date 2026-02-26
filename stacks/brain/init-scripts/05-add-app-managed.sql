-- Migration: Add app_managed column to agent_state and llm_models
-- app_managed = true means the row was edited via API/UI and sync should skip it.

DO $$
BEGIN
    -- Add app_managed to agent_state if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'aria_engine'
          AND table_name = 'agent_state'
          AND column_name = 'app_managed'
    ) THEN
        ALTER TABLE aria_engine.agent_state
            ADD COLUMN app_managed BOOLEAN DEFAULT false;
        RAISE NOTICE 'Added app_managed to aria_engine.agent_state';
    END IF;

    -- Add app_managed to llm_models if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'aria_engine'
          AND table_name = 'llm_models'
          AND column_name = 'app_managed'
    ) THEN
        ALTER TABLE aria_engine.llm_models
            ADD COLUMN app_managed BOOLEAN DEFAULT false;
        RAISE NOTICE 'Added app_managed to aria_engine.llm_models';
    END IF;
END $$;
