---
name: nourish-product-playbook
description: Nourish-specific product rules for meal prep, batch cooking, weekly planning, grocery lists, and nutrition-safe UX. Use whenever the work is in the Nourish app or touches meal planning, grocery, recipes, or nutrition features.
---

# Nourish Product Playbook

## Use when

- The repo is `nourish-production` or the task names Nourish.
- The work involves meal prep, weekly planning, recipes, grocery, pantry,
  nutrition, or dietary constraints.

## Domain rules (enforce these)

1. **The week is the unit.** Plans, grocery, prep are weekly. Daily views
   are derived.
2. **Grocery list = plan minus pantry.** Never ask the user to build it
   manually when a plan exists.
3. **Aggregate by ingredient and aisle.** One line per ingredient; group
   by store aisle.
4. **Substitutions are first-class.** Out-of-ingredient is a fork, not an
   error.
5. **Dietary constraints are hard filters.** Allergens, religious, and
   medical restrictions never appear, even as alternatives.
6. **Servings scale cleanly.** Round to usable units; never show "0.5
   egg".
7. **Prep time is honest.** Active + passive both shown.
8. **Leftovers are planned.** Day-two and day-three usage visible at plan
   time.
9. **Nutrition is informative, not prescriptive.** No calorie-gatekeeping
   unless the user opted in.
10. **Sunday cognition is low.** Plan-confirm is one-handed on a phone.

## Refused patterns

- Streaks that punish a missed cooking week.
- Calorie-shaming copy.
- Premium upsells inside a grocery list.
- Recipes requiring obscure ingredients without substitutes.
- "Add to cart" integrations that silently swap brand/size.

## Output

```
## Surface
## Domain-rule violations found (with file:line or screenshot)
## Anti-patterns found
## Retention risk (1–5) with reason
## Recommended changes (specific copy, layout, behavior)
## Owner-only changes (nutrition data, store integrations, legal)
## Verdict: SHIP | POLISH | RETHINK
```
