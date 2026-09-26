# Boxtide (demo app)

A 13-screen order-support Flutter app used as the test target for the runner in
`../runner`. Every interactive widget carries a `Key` and a Semantics
`identifier`. A chaos mode, exposed as the `ext.flutter.boxtide.setChaos`
service extension, renames keys, swaps labels and reorders lists by seed.

```bash
flutter run -d macos
```

Boxtide is a fictional shop made up for this repo; the brand, products and order
numbers do not refer to any real company.
