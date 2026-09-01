# Frame Patcher

**Version 1.4**

Скилл для ChatGPT и Codex, который точечно чинит, заменяет или добавляет объекты в изображение без перегенерации всего кадра.

Для ремонта существующего дефекта он вырезает проблемную область с контекстом, передаёт редактору кроп и точную маску, а затем возвращает исправление в неизменяемый исходник. Для добавления нового объекта работает иначе: сначала генерирует его в достаточно большом контекстном кропе, после генерации строит маску по реальному силуэту и сохраняет только объект, контактную тень и необходимые отражения.

Техническая проверка защищает пиксели вне разрешённой зоны, а отдельная визуальная приёмка проверяет геометрию, силуэты, швы, масштаб, опору и смысловую правильность результата.

Полезен для рук, лиц, надписей, мелких объектов, швов и AI-артефактов, а также для аккуратного добавления новых объектов — особенно когда полнокадровая правка начинает шакалить хороший исходник.

В версии 1.4 добавлены:

- обязательная команда `stage` перед композитом в режимах repair, replace и integrate;
- checkerboard, protected-overlay и side-by-side для проверки регистрации кропа;
- запрет на скрытое растяжение, кроп и подгонку редакторского результата;
- требование маскировать весь заменяемый объект вместе с остатками, зависимым прозрачным блистером и отражениями;
- блокировка `compose`, если редакторский кроп не зарегистрирован и явно не принят;
- двухступенчатая команда `verify`: техническая проверка и отдельный ручной визуальный допуск;
- запрет выдачи результата, пока `visual_acceptance` не установлен в `pass`.

## Что внутри

- `SKILL.md` — логика, маршрутизация режимов и рабочий пайплайн.
- `scripts/patch_tools.py` — подготовка кропов, масок, композитинг и проверка.
- `references/additive.md` — добавление новых объектов через post-generation masking.
- `references/visual-acceptance.md` — приёмка сложных реконструкций и связанных объектов.
- `agents/openai.yaml` — интерфейс скилла.
- `assets/icon.svg` — иконка.

Скрипт использует Python, Pillow и NumPy. Для автоматического поиска увеличенного кропа нужен SciPy.

## English

Frame Patcher is a ChatGPT and Codex skill for repairing, replacing, or adding a localized element without regenerating or degrading the entire image.

For repairs and replacements, it prepares a contextual crop and an exact edit mask before generation. For new objects, the additive workflow generates inside a sufficiently large contextual crop and derives the mask from the actual generated silhouette.

Version 1.4 adds a mandatory registration stage before compositing repair, replacement, or integration edits. Editor outputs may not be silently stretched, cropped, or resized into place. Registration is reviewed with checkerboard, protected-overlay, and side-by-side artifacts, and delivery remains blocked until both technical verification and explicit visual acceptance pass.

Technical verification protects pixels outside the authorized region. A separate visual gate checks geometry, silhouette integrity, scale, contact, seams, and semantic correctness. A technically safe composite is never presented as successful until the edited or added object also passes visual review.

### Repository contents

- `SKILL.md` — routing, workflows, constraints, and stopping rules.
- `scripts/patch_tools.py` — crop preparation, pre-generation and post-generation masks, compositing, and verification.
- `references/additive.md` — additive workflow and post-generation masking.
- `references/visual-acceptance.md` — acceptance guidance for reconstruction and dependent objects.
- `agents/openai.yaml` — skill interface metadata.
- `assets/icon.svg` — skill icon.

## Автор

Alexander Dobrokotov / [AI Molodca](https://aimolodca.com)  
Telegram: [t.me/strangedalle](https://t.me/strangedalle)
