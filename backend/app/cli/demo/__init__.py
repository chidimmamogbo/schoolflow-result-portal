"""The demo seed (BUILD_PROMPT 9.2v; ACCEPTANCE_TESTS fixtures; D-180).

It builds three fictional schools the way people would: it signs in as each
person and calls the app's own routes inside this process, so every rule and
database check runs (Chidimma's choice). Every demo account ends up with the
one password in SEED_PASSWORD, which is never printed or stored in git.

- `browser.py`: a signed-in person (cookie, CSRF header, plain errors).
- `platform.py`: the super admin, the price list, the schools and principals.
"""
