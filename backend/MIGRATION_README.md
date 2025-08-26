# Миграции для исправления NULL значений в total_fees и total_trans

## Проблема
В базе данных обнаружены токены с NULL значениями в полях `total_fees` и `total_trans`, что нарушает ограничения NOT NULL.

## Решение
Созданы три миграции для пошагового исправления:

### 1. 0014_fix_total_fees_null.py
- Обновляет все NULL значения в `total_fees` на 0.0

### 2. 0015_fix_total_trans_null.py  
- Обновляет все NULL значения в `total_trans` на 0

### 3. 0016_add_not_null_constraints.py
- Добавляет ограничения NOT NULL на поля `total_fees` и `total_trans`

## Применение миграций

```bash
cd backend
python manage.py migrate mainapp
```

## Проверка результата

После применения миграций проверьте, что все токены имеют корректные значения:

```sql
-- Проверка total_fees
SELECT COUNT(*) FROM mainapp_token WHERE total_fees IS NULL;

-- Проверка total_trans  
SELECT COUNT(*) FROM mainapp_token WHERE total_trans IS NULL;
```

Оба запроса должны возвращать 0.

## Предотвращение будущих проблем

В коде исправлены все места создания токенов:
- `backend/flip/create.py` - добавлены значения по умолчанию
- `backend/flip/process.py` - улучшена обработка ошибок API
- `backend/flip/old_process.py` - аналогичные исправления
- `tests2/flip/create_db.py` - добавлены значения по умолчанию
- `tests2/flip/process_users.py` - добавлены значения по умолчанию

Теперь все новые токены будут создаваться с корректными значениями по умолчанию. 