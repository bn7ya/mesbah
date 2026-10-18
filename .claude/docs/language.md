# Language — how every word a user reads is written

Rule 22 in `CLAUDE.md`. This is the standard for every user-facing string, in Arabic and
in English: bundle values, seeded `_ar` columns, error messages, labels, tooltips, empty
states. `copywriter` and `translator` write to it, `unifier` keeps its vocabulary, and
the guard hook enforces the one rule a regex can see.

It exists because a bilingual interface written English-first drifts the same way every
time: the Arabic becomes a word-for-word rendering of English that was itself over-written.
Diacritics appear because the chosen word needs one to be read; counts break because
"{n} items" has no plural rule behind it; titles stop naming their pages; every note
argues with a reader who was not doubting anything.

## The rules

1. **Each language is written as a native product would write it.** The Arabic is not a
   translation of the English and the English is not a translation of the Arabic. Both say
   the same thing; neither carries the other's word order, idiom or punctuation.
2. **No tashkeel.** No diacritic (U+064B to U+0652, U+0670) in any Arabic value. A word
   that needs a vowel mark to be read is the wrong word: "خضع لمراجعة بشرية", never
   "مراجَع"; "لم يتم التحقق منه بعد", never "غير مُتحقَّق منه". Replace the word, do not
   strip the mark. Where a passive verb would need a mark, «تم / تمت + المصدر» is the
   readable form («تمت إعادة», «تم تسجيل»); where an active verb reads unambiguously,
   prefer the verb («تحفظ كل مدينة على حدة», not «يتم الحفظ»).
3. **The product has no intent.** It does not ask, read, refuse, land, look, judge or
   decide, and it never speaks in the first person. A result is a result, an error is a
   state. "اطرح سؤالا وتعرض الإجابات هنا", never "ستحط الإجابات هنا".
4. **No aside for a sceptic.** Nobody on screen is doubting the product, so nothing on
   screen argues: no "rather than", "instead of", "not a fault in the page", "not a list
   somebody wrote", "on purpose", "which is useful but not the same thing". Say what is
   on the screen. If a caveat matters it is one short sentence of its own, and it states
   a fact, not a defence.
5. **Short.** A title is a noun phrase. A note, hint or empty state is one or two
   sentences, each under fifteen words. No em-dash asides, no semicolons, no colon
   followed by a lecture, no metaphor.
6. **A title names the page.** The reader must know from the title alone what they are
   looking at. A nav label carries the same name as the page it opens.
7. **A count never precedes a noun.** Unless the runtime has real plural rules, "{n}
   items" and "{n} عنصرا" are both wrong for most values of n. Write `label: {n}`
   ("عدد العناصر: {count}", "Items: {count}") or `{n} of {total}`. The one exception is a
   fixed window between 11 and 99 ("آخر {days} يوما", "the last {days} days"), which
   Arabic counts with the singular and English with the plural.
8. **No bare jargon.** A technical term is either replaced by the word a reader uses or
   spelled out once. A model, algorithm, library or user-agent name never renders to a
   user. Mesbah's exception is below under "Technical terms" (ADR-007).
9. **The backend sends keys, not prose.** An error carries a stable `code` and the
   frontend resolves `errors.<code>`; seeded prose with a stable key resolves through a
   key with the server's text as fallback. A sentence the frontend prints verbatim from
   the server is a bug in whichever language it arrives.
10. **One word per concept.** The vocabulary below is the list. A second word for the same
    thing, in either language, is a divergence `unifier` removes.

## Vocabulary

Grow this table from the first feature. One row per concept, both languages, no synonyms.

| Concept | Arabic | English |
|---|---|---|
| a person with an account | مستخدم | user |
| reviewed by a person | خضع لمراجعة بشرية | reviewed by a person |
| not yet verified | لم يتم التحقق منه بعد | not yet verified |
| a filter control | تصفية | filter |

## Technical terms

Mesbah only (ADR-007). Model, dataset and engine names render as their publishers write
them, with `dir="ltr"` on the name. These terms stay in English in both languages, each with
an `<app-term>` explanation in the reader's language:

LoRA · QLoRA · GPU · VRAM · RAM · CPU · loss · learning rate · token · MoE · GGUF ·
safetensors · API · API key

| Concept | Arabic | English |
|---|---|---|
| the product | مصباح | Mesbah |
| a model being customized | مشروع | project |
| a node in a project's tree | نسخة | version |
| the change a version stores | التغيير | change |
| the model a project starts from | النموذج الأساسي | base model |
| a chat with a version | محادثة | conversation |
| the model's reasoning before a reply | سلسلة التفكير | thinking |
| changing a reply or thinking | تعديل | edit |
| the marker on a changed reply | تم التعديل | edited |
| an install-wide data entry | مجموعة بيانات | dataset |
| turning data into a version | تدريب | training |
| a server a version runs on | محرك | engine |

## What a native reader rejects

Arabic:

- **الخاص بك** for "your": drop it. "اسم المستخدم", not "اسم المستخدم الخاص بك".
- **قم بـ + verbal noun**: the verbal noun alone. "حفظ التغييرات", not "قم بحفظ التغييرات".
- **بدل أن / لا من / وليس** contrasts: delete the contrast and keep the fact.
- **A chain of subordinate clauses** carried over from English: one clause, one sentence.
- **A passive participle that needs a shadda**: replace with a verb phrase.
- **Impersonal passives** ("كيف يُتحدث عن"): name the subject. "ماذا قيل عن".
- **A particle glued to a placeholder** («بـ{count}», «الـ{count}»): restructure as `label: {n}`.
- **English punctuation habits**: no em-dash, no semicolon; the Arabic comma and full stop.

English:

- "rather than", "instead of", "on purpose", "deliberately", "still" as reassurance.
- "not a fault in the page", "which is X rather than Y".
- "we don't", "it cannot", "never" as policy statements inside a label.
- An em-dash aside or a semicolon joining two thoughts that wanted two sentences.
- A verb that gives the software a mind: it asked, it refused, it read, it decided.

## The loop

1. `translator` writes the Arabic **from the meaning**, with the English closed. It then
   reads the Arabic without the English beside it and asks whether a native professional
   would have written that sentence in a product of their own.
2. `copywriter` writes the English to say the same thing, plainly, and reads the Arabic
   against the rules above. It pushes back on any string that fails one; the translator
   rewrites; the copywriter re-reads.
3. `user_journey_engineer` switches the locale to Arabic and walks every page it tests,
   reading titles and notes as a reader would. A key on screen, an English sentence, a
   diacritic or a count before a noun is a finding.
4. `unifier` sweeps both bundles for vocabulary drift and adds to the table above.

## What is mechanical

- The guard hook blocks an edit that writes a diacritic into an `ar.json` or a migration.
- CI (`i18n` job) checks identical key sets and no tashkeel in any `ar.json` value.
  Placeholder parity and "still in English" checks are worth adding once bundles exist.
- Everything else is judgement, which is why the loop exists.
