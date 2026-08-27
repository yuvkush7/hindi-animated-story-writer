# Dialogue Rules

## THE ABSOLUTE RULE

**Every spoken line must identify its speaker in bold, in this exact form:**

```
**नाम:** "संवाद यहाँ..."
```

There are **no exceptions.** A line of dialogue without an explicit, bold speaker attribution is invalid and must be fixed before final output. This rule exists because downstream, each spoken line becomes an audio beat with a `speaker`, and the HTML Studio highlights the current speaker's line — un-attributed dialogue breaks the entire audio pipeline.

## Correct vs. incorrect

### ✅ Correct

```
**तितली:** "यह मीनार रात में क्यों चमकती है?"
**गोलू:** "मुझे नहीं पता, पर मुझे डर लग रहा है!"
```

### ❌ Incorrect

```
"यह मीनार रात में क्यों चमकती है?"
"मुझे नहीं पता, पर मुझे डर लग रहा है!"
```

The incorrect version has no speaker — it cannot be turned into audio and cannot be highlighted in the Studio.

### ❌ Also incorrect (attribution not in bold / not tagged)

```
तितली ने पूछा — यह मीनार रात में क्यों चमकती है?
```

Narrative attribution ("तितली ने पूछा") is fine as prose, but the **spoken line itself** must still carry the `**नाम:**` tag.

## Unknown speakers

When the speaker's identity is a mystery, still attribute the line explicitly, using a descriptive tag:

```
**रहस्यमयी आवाज़:** "जो मीनार में घुसेगा, वापस नहीं आएगा..."
```

Other useful unknown-speaker tags: `**अनजान आवाज़:**`, `**छिपा हुआ व्यक्ति:**`. Reveal the true identity later, at the reveal.

## Narration

Narration is attributed to the narrator:

```
**कथावाचक:** "सूरज ढल चुका था और गाँव पर एक अजीब सी खामोशी छा गई थी।"
```

## Validation requirement

Before any story is considered final, **speaker attribution must be validated**:

- Every spoken line has a `**नाम:**` tag (or a descriptive unknown-speaker tag).
- Every narration line is tagged `**कथावाचक:**`.
- Every attributed speaker maps to a known character `id` (or an intentional unknown-speaker label).

Stories that fail this validation are not exported to script, HTML, or audio.
