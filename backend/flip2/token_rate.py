import math

# === КОНФИГУРАЦИЯ / ЭТАЛОННЫЕ ЗНАЧЕНИЯ ===
# Эти значения нужно будет настроить на основе анализа данных
# 1. Бенчмарки для токенов
BENCHMARK_TOTAL_TRANS = 300   # Эталонное количество транзакций
BENCHMARK_ATH = 3000         # Эталонное значение ATH ($)

DEV_TOKENS_STRICTNESS_COEF = 0.5 # Чем больше, тем строже наказание за отклонение от 1

IDEAL_MIGRATION_PERCENT = 10.0 # Процент, при котором полезность максимальна (100%)

# 4. Параметры для токенов твиттера
TWITTER_TOKENS_IDEAL_MIN = 7
TWITTER_TOKENS_IDEAL_MAX = 200
TWITTER_TOKENS_IDEAL_PEAK = 40 

def calculate_token_rating(
    last_3_tokens_data,  # Список из 3х словарей: [{'total_trans': int, 'ath': float}, ...]
    dev_total_tokens,    # int - общее количество токенов, связанных с адресом разработчика
    twitter_migration_percent, # float - процент миграций твиттер-аккаунта (например, 5.0)
    twitter_total_tokens # int - общее количество токенов, связанных с твиттер-аккаунтом
) -> float:
    """
    Рассчитывает рейтинг мем-токена по 100-бальной шкале на основе переданных данных.

    Args:
        last_3_tokens_data: Данные последних 3х токенов.
        dev_total_tokens: Total tokens разработчика.
        twitter_migration_percent: Процент миграций твиттера.
        twitter_total_tokens: Total tokens твиттера.

    Returns:
        float: Итоговый рейтинг от 0.0 до 100.0.
    """
    
    # 1. РАСЧЕТ ЧАСТИ РЕЙТИНГА ОТ ТОКЕНОВ (60%)
    token_utility_trans = []  # Полезность по транзакциям для каждого токена
    token_utility_ath = []    # Полезность по ATH для каждого токена

    for token in last_3_tokens_data:
        # Для каждого токена считаем полезность по total_trans
        # Используем корень для убывающей полезности и ограничиваем сверху (200)
        trans_ratio = token['total_trans'] / BENCHMARK_TOTAL_TRANS
        utility_trans = min(200, math.sqrt(trans_ratio) * 100)
        token_utility_trans.append(utility_trans)

        # Для каждого токена считаем полезность по ATH
        ath_ratio = token['ath'] / BENCHMARK_ATH
        utility_ath = min(200, math.sqrt(ath_ratio) * 100)
        token_utility_ath.append(utility_ath)

    # Усредняем полезность по трем токенам для каждого параметра
    avg_utility_trans = sum(token_utility_trans) / len(token_utility_trans)
    avg_utility_ath = sum(token_utility_ath) / len(token_utility_ath)

    # Объединяем оба параметра (50/50) и применяем вес 60%
    tokens_final_score = (avg_utility_trans * 0.5 + avg_utility_ath * 0.5) * 0.6

    # 2. РАСЧЕТ ЧАСТИ РЕЙТИНГА ОТ ТОКЕНОВ РАЗРАБОТЧИКА (15%)
    # Функция "перевернутого холма" с пиком в 1
    deviation = abs(dev_total_tokens - 1)
    dev_tokens_utility = max(0, 100 * (1 - (deviation * DEV_TOKENS_STRICTNESS_COEF)))
    dev_tokens_score = dev_tokens_utility * 0.15

    # 3. РАСЧЕТ ЧАСТИ РЕЙТИНГА ОТ МИГРАЦИЙ ТВИТТЕРА (15%)
    # Линейный рост до IDEAL_MIGRATION_PERCENT, потом плато
    migration_utility = min(100, (twitter_migration_percent / IDEAL_MIGRATION_PERCENT) * 100)
    migration_score = migration_utility * 0.15

    # 4. РАСЧЕТ ЧАСТИ РЕЙТИНГА ОТ ТОКЕНОВ ТВИТТЕРА (10%)
    # Функция "холма" с идеальным диапазоном
    if twitter_total_tokens < TWITTER_TOKENS_IDEAL_MIN:
        # Линейный рост от 0 до 50 при приближении к минимуму
        twitter_tokens_utility = (twitter_total_tokens / TWITTER_TOKENS_IDEAL_MIN) * 50
    elif TWITTER_TOKENS_IDEAL_MIN <= twitter_total_tokens <= TWITTER_TOKENS_IDEAL_MAX:
        # Пиковая зона: рассчитываем близость к идеалу (55)
        # Нормируем разницу от пика к границам диапазона
        range_to_min = TWITTER_TOKENS_IDEAL_PEAK - TWITTER_TOKENS_IDEAL_MIN
        range_to_max = TWITTER_TOKENS_IDEAL_MAX - TWITTER_TOKENS_IDEAL_PEAK
        # Берем максимальный из двух диапазонов для симметричности
        max_range = max(range_to_min, range_to_max)
        
        # Рассчитываем полезность на основе расстояния до пика
        distance_to_peak = abs(twitter_total_tokens - TWITTER_TOKENS_IDEAL_PEAK)
        # Чем дальше от пика, тем меньше полезность (линейно)
        twitter_tokens_utility = 100 * (1 - (distance_to_peak / max_range))
        # Обеспечиваем, чтобы полезность не упала ниже 50 на границах
        twitter_tokens_utility = max(50, twitter_tokens_utility)
    else:
        # Если больше идеального максимума - резкое падение
        twitter_tokens_utility = max(0, 100 - (twitter_total_tokens - TWITTER_TOKENS_IDEAL_MAX))
    
    twitter_tokens_score = twitter_tokens_utility * 0.10

    # ФИНАЛЬНЫЙ РЕЙТИНГ (сумма всех частей)
    final_rating = (
        tokens_final_score +
        dev_tokens_score +
        migration_score +
        twitter_tokens_score
    )

    # Обеспечиваем, чтобы рейтинг был в пределах [0, 100]
    return max(0, min(100, final_rating))

# === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===
if __name__ == "__main__":
    # Тестовые данные
    test_tokens = [
        {'total_trans': 44, 'ath': 911},
        {'total_trans': 39, 'ath': 1300},
        {'total_trans': 10, 'ath': 377}
    ]
    
    dev_tokens = 87
    migration_percent = 0
    twitter_tokens = 15
    
    rating = calculate_token_rating(
        test_tokens,
        dev_tokens,
        migration_percent,
        twitter_tokens
    )
    
    print(f"Рассчитанный рейтинг: {rating:.2f}/100")