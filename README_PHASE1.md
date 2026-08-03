# ШТАБ AI — этап 1: модели, токены и бесплатные генерации

## Что заменять

Скопируйте файлы из архива в корень проекта с сохранением путей:

- `model_catalog.py` — новый файл;
- `services/billing_service.py` — новый файл;
- `services/genapi_client.py` — новый файл;
- `services/generation_service.py` — новый файл;
- `database.py` — заменить;
- `settings.py` — заменить.

Перед заменой сделайте резервную копию базы данных.

## Что реализовано

- по одной бесплатной генерации текста, изображения и видео для нового пользователя;
- после бесплатной попытки — атомарное списание внутренних токенов;
- автоматический возврат токенов/попытки при ошибке API;
- история операций в `token_transactions`;
- изменяемые цены моделей в таблице `model_prices`;
- единый каталог всех выбранных текстовых, Flux- и видеомоделей;
- единый клиент GenAPI;
- пакеты: 500/199 ₽, 1500/499 ₽, 4000/999 ₽, 10000/1999 ₽;
- ключ API больше не печатается в консоль.

## Важно

Этот этап создаёт ядро. Старые обработчики `handlers.py` ещё не переключены на
`generation_service`; это будет этап 2. До переключения интерфейс бота продолжит
использовать старую логику генераций.

Таблицы `free_generation_credits` и `model_prices` создаются автоматически при
запуске. Существующим пользователям бесплатные попытки также будут созданы при
первом обращении к новому биллингу.

## Пример использования

```python
from services.generation_service import generation_service

result = await generation_service.generate_text(
    user_id=message.from_user.id,
    model_key="deepseek-v4-flash",
    messages=[{"role": "user", "content": message.text}],
)

charge, task = await generation_service.create_media_task(
    user_id=message.from_user.id,
    model_key="flux-dev",
    prompt="Портрет в кинематографическом стиле",
    input_image=None,
)
```

## Проверка

```bash
python -m py_compile \
  model_catalog.py settings.py database.py \
  services/billing_service.py \
  services/genapi_client.py \
  services/generation_service.py
```
