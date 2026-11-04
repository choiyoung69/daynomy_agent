# Independent React Native test author

The test role wrote the public stub and 27 source-derived contract tests before implementation. `red.log` is the real Node execution on empty stub; `frozen.json` records the immutable tests SHA256 and the initial stub SHA256. The RED command returned 1: 27 tests, 21 fail, 6 rejection-only passes; zero skipped. Invalid-input tests that only assert a throw necessarily pass against an always-throw stub, so this partial number is not implementation success.

Run from repository root:

```sh
node --experimental-strip-types --test clients/react-native/tests/core.test.ts
```

The stub is now owned by the implementation role. Test author does not modify implementation or fixed tests after release. Additional verification evidence belongs in separate independent-verifier files. `spec/react-native/core-contract.md` explains the mapping and explicit mobile write-replay difference from web; `spec/react-native/verification-plan.md` separates actual Node/HTTP/build/device evidence.
