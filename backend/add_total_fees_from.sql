-- Добавление поля total_fees_from в таблицу mainapp_settings
ALTER TABLE mainapp_settings ADD COLUMN total_fees_from DECIMAL(16,8) DEFAULT 0;

-- Обновление существующих записей
UPDATE mainapp_settings SET total_fees_from = 0 WHERE total_fees_from IS NULL; 