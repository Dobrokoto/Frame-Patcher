# Frame Patcher

**Version 1.1**

Скилл для ChatGPT и Codex, который точечно чинит отдельные участки изображения без перегенерации всего кадра.

Он вырезает проблемную область с контекстом, передаёт редактору кроп и точную маску, а затем возвращает исправление в неизменяемый исходник. Техническая проверка защищает пиксели вне разрешённой зоны, а отдельная визуальная приёмка проверяет геометрию, силуэты, швы и смысловую правильность ремонта.

Полезен для рук, лиц, надписей, мелких объектов, швов и AI-артефактов — особенно когда полнокадровая правка начинает шакалить хороший исходник.

В версии 1.1 добавлены:

- классификация обычного ремонта, логически выводимой правки и реконструкции скрытых областей;
- source-native polygon masks и предупреждения для рискованных bbox-масок;
- адаптивная растушёвка для жёстких и мягких границ;
- инварианты, защищённые и неопределённые зоны;
- QA contact sheet, проверка контура и раздельные технический/визуальный статусы;
- обязательная смена стратегии после повторяющихся неудач.

## Что внутри

- `SKILL.md` — логика и рабочий пайплайн.
- `scripts/patch_tools.py` — подготовка кропов и масок, композитинг и проверка.
- `references/visual-acceptance.md` — приёмка сложных реконструкций и связанных объектов.
- `agents/openai.yaml` — интерфейс скилла.
- `assets/icon.svg` — иконка.

Скрипт использует Python, Pillow и NumPy. Для автоматического поиска увеличенного кропа нужен SciPy.

## English

Frame Patcher is a ChatGPT and Codex skill for repairing a known local defect without regenerating or degrading the entire image. It prepares a contextual crop and an exact edit mask, sends only that crop to the image editor, composites the accepted result back into the immutable source, and verifies pixel protection outside the authorized area.

Version 1.1 distinguishes straightforward repairs from inferred edits and uncertain reconstruction of hidden geometry. It adds source-native polygon masks, adaptive feathering, task invariants, protected and uncertain regions, boundary inspection, a QA contact sheet, and separate technical and visual acceptance gates. A technically safe composite is never presented as a successful repair until the edited object also passes visual review.

The skill is useful for malformed hands and faces, text, signs, small objects, silhouettes, seams, occluder removal, and AI artifacts—especially when repeated full-frame edits would damage an otherwise strong image.

### Repository contents

- `SKILL.md` — routing, workflow, constraints, and stopping rules.
- `scripts/patch_tools.py` — crop preparation, exact masks, compositing, and verification.
- `references/visual-acceptance.md` — acceptance guidance for reconstruction and dependent objects.
- `agents/openai.yaml` — skill interface metadata.
- `assets/icon.svg` — skill icon.

## Автор

Alexander Dobrokotov / [AI Molodca](https://aimolodca.com)  
Telegram: [t.me/strangedalle](https://t.me/strangedalle)
