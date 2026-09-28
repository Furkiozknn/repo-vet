## Ne degisti? (What changed?)

<!-- Short and specific. The "why" goes below. -->

## Neden? (Why?)

<!-- Which problem, which issue, which real repository showed it? -->

## Nasil dogrulandi? (How was it verified?)

<!-- The command you ran and what it printed. "Tests pass" is not enough. -->

```
# e.g. PYTHONPATH=. python -m unittest discover -s tests -p "test_*.py"  ->  Ran N tests ... OK
```

## Kontrol listesi (Checklist)

- [ ] The suite passes locally, and no test touches the network
- [ ] New behaviour has a test; a fix has a test that fails without it
- [ ] README / CHANGELOG updated where behaviour changed
- [ ] No new runtime dependency
