# Language — how every word a user reads is written

The `Language` section of the root `CLAUDE.md`. This is the standard for every
user-facing string: the Arabic the UI renders, the English technical terms that
stay English, error messages, labels, tooltips, empty states. `copywriter` and
`translator` write to it, `unifier` keeps its vocabulary, and the guard hook
enforces the one rule a regex can see.

Mesbah is **Arabic, RTL, single-language**. Today that means Arabic strings
inline in each component's template; at the Angular-22 cutover they move to
`ar.json`/`en.json` bundles and the mechanical checks below start biting. The
standard is the same in both shapes.

It exists because an Arabic interface written from English drifts the same way
every time: the Arabic becomes a word-for-word rendering of English that was
itself over-written. Diacritics appear because the chosen word needs one to be
read; counts break because "{{n}} عناصر" has no plural rule behind it; titles
stop naming their pages; every note argues with a reader who was not doubting
anything.

## The rules

1. **Arabic is written as a native product would write it.** Not a translation
   of an English sentence. It does not carry English word order, idiom or
   punctuation.
2. **No tashkeel.** No diacritic (U+064B to U+0652, U+0670) in any Arabic a
   user reads. A word that needs a vowel mark to be read is the wrong word:
   "خضع لمراجعة بشرية", never "مراجَع"; "لم يتم التحقق منه بعد", never
   "غير مُتحقَّق منه". Replace the word, do not strip the mark. Where a
   passive verb would need a mark, «تم / تمت + المصدر» is the readable form
   («تمت إعادة», «تم تسجيل»); where an active verb reads unambiguously,
   prefer the verb. The product name «مِصباح» is the one string that keeps
   its kasrah — it is a name, not a word to be read.
3. **The product has no intent.** It does not ask, read, refuse, land, look,
   judge or decide. A result is a result, an error is a state.
   "اطرح سؤالا وتظهر الإجابات هنا", never "ستحط الإجابات هنا".
4. **No aside for a sceptic.** Nobody on screen is doubting the product, so
   nothing on screen argues: no «بدل أن», «لا من», «وليس», «عن قصد», «ليست
   خطأ في الصفحة». Say what is on the screen. If a caveat matters it is one
   short factual sentence of its own, not a defence.
5. **Short.** A title is a noun phrase. A note, hint or empty state is one or
   two sentences, each under fifteen words. No em-dash asides, no semicolons,
   no colon followed by a lecture, no metaphor.
6. **A title names the page.** The reader must know from the title alone what
   they are looking at. A nav label carries the same name as the page it opens.
7. **A count never precedes a noun.** The runtime has no plural rules, so
   «{{n}} عنصرا» is wrong for most values of n. Write `label: {{n}}`
   ("عدد العناصر: {{count}}") or «{{done}} من {{total}}». The one exception is
   a fixed window between 11 and 99 ("آخر {{days}} يوما"), which Arabic counts
   with the singular.
8. **No bare jargon** beyond the technical terms that stay English on purpose.
   A raw `null`, a status code, an exception class name or an English error
   string pasted into a label is a bug.
9. **One word per concept.** The vocabulary below is the list. A second word
   for the same thing is a divergence `unifier` removes.
10. **Seeded prose is copy.** A row's `description_ar`, a label a reader sees
    from the database, and every server-side message a user can see —
    FastAPI validation text today, the Django side's error envelope with its
    stable `code` and prose beside an English column at the migration — is
    copy. It travels to the UI, so it is written to this standard.

## Vocabulary

Grow this table from the first feature. One row per concept, Arabic and the
English technical term where one exists, no synonyms.

| Concept | Arabic | English |
|---|---|---|
| a fine-tuning run | تدريب | training run |
| a model version | إصدار | version |
| a correction to an answer | تصحيح | correction |
| the model's thinking chain | سلسلة التفكير | thinking chain |

## What a native reader rejects

- **الخاص بك** for "your": drop it. "اسم المستخدم", not "اسم المستخدم الخاص بك".
- **قم بـ + verbal noun**: the verbal noun alone. "حفظ التغييرات", not
  "قم بحفظ التغييرات".
- **بدل أن / لا من / وليس** contrasts: delete the contrast and keep the fact.
- **A chain of subordinate clauses** carried over from English: one clause,
  one sentence.
- **A passive participle that needs a shadda**: replace with a verb phrase.
- **An impersonal passive** («كيف يُتحدث عن»): name the subject. «ماذا قيل عن».
- **A particle glued to a placeholder** («بـ{{count}}», «الـ{{count}}»):
  restructure as `label: {{n}}`.
- **English punctuation habits**: no em-dash, no semicolon; the Arabic comma
  and full stop.
- **A verb that gives the software a mind**: it asked, it refused, it read,
  it decided.

## The loop

1. `copywriter` writes the Arabic as a professional Arabic speaker would write
   it in a product of their own, and reads it back on its own and asks whether
   that reader would have written the sentence.
2. `translator` sweeps the RTL layout and the English-technical-term boundary,
   and checks the new Arabic against the rules above.
3. `user_journey_engineer` walks the running app and reads titles and notes as
   a reader would. A key on screen, a diacritic, a technical term rendered in
   the wrong direction or a count before a noun is a finding.
4. `unifier` sweeps for vocabulary drift and adds to the table above.

## What is mechanical

- The guard hook blocks an edit that writes a diacritic into an `ar.json`
  catalogue or a seed migration.
- CI (`i18n` job) checks that `ar.json` sits beside every `en.json` with an
  identical key set and no tashkeel in any Arabic value.
- Until the cutover, the app's Arabic is inline in templates and outside the
  regex's reach — there the `translator` sweep and the `copywriter` re-read
  are the check. Existing template strings predate this standard; when a
  string is rewritten, it is written to it.
- Everything else is judgement, which is why the loop exists.
