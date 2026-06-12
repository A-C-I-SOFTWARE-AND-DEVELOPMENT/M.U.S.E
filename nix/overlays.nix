# nix/overlays.nix — Expose pkgs.muse-agent (and the permanent legacy alias
# pkgs.hermes-agent) for external NixOS configs
{ inputs, ... }:
{
  flake.overlays.default = final: _: {
    muse-agent = final.callPackage ./muse-agent.nix {
      inherit (inputs) uv2nix pyproject-nix pyproject-build-systems;
      npm-lockfile-fix = inputs.npm-lockfile-fix.packages.${final.stdenv.hostPlatform.system}.default;
      rev = inputs.self.rev or null;
    };
    # Permanent legacy alias (Hermes -> MUSE rename) — same derivation.
    hermes-agent = final.muse-agent;
  };
}
