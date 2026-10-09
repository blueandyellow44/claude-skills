// secure-gate.mjs - deploy-script gate, generalized from a production app's deploy script
// scripts/deploy-site.mjs (2026-10-07): refuse BEFORE building when the
// security tests or the secure-launch gate fail. Import it at the top of the
// deploy script:
//
//   import { secureGate } from "./secure-gate.mjs";
//   secureGate({ root: ROOT, testCommand: ["npm", "run", "-s", "test:api"] });
//   // ...build and deploy only after this line
//
// Exits the process with status 1 on refusal; returns nothing on success.
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export function secureGate({ root, testCommand, ledger = true }) {
  const refuse = (why) => {
    console.error(`secure-gate: deploy refused: ${why}`);
    process.exit(1);
  };
  if (testCommand) {
    const [cmd, ...args] = testCommand;
    const t = spawnSync(cmd, args, { cwd: root, stdio: "inherit" });
    if (t.status !== 0) refuse(`${testCommand.join(" ")} failed`);
  }
  if (ledger) {
    const out = mkdtempSync(join(tmpdir(), "secure-launch-"));
    try {
      spawnSync("python3", [join(root, ".secure-launch/secure-core/scripts/secure_launch.py"), root, "--out", out], { stdio: "ignore" });
      const g = spawnSync("python3", [join(root, ".secure-launch/secure-gate/scripts/gate.py"), join(out, "findings.json"), "--repo", root], { stdio: "inherit" });
      if (g.status !== 0) refuse("the secure-launch gate did not pass");
    } finally {
      rmSync(out, { recursive: true, force: true });
    }
  }
}
