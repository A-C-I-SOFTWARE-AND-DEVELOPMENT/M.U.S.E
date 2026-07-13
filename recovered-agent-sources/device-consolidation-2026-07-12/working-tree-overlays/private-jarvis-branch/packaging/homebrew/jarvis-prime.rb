class JarvisPrime < Formula
  include Language::Python::Virtualenv

  desc "JARVIS Prime local-first personal AI operating partner"
  homepage "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent"
  # Stable source should point at the semver-named sdist asset attached by
  # scripts/release.py, not the CalVer tag tarball.
  url "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/releases/download/v2026.3.30/jarvis_prime-0.6.0.tar.gz"
  sha256 "<replace-with-release-asset-sha256>"
  license "MIT"

  depends_on "certifi" => :no_linkage
  depends_on "cryptography" => :no_linkage
  depends_on "libyaml"
  depends_on "python@3.14"

  pypi_packages ignore_packages: %w[certifi cryptography pydantic]

  # Refresh resource stanzas after bumping the source url/version:
  #   brew update-python-resources --print-only jarvis-prime

  def install
    venv = virtualenv_create(libexec, "python3.14")
    venv.pip_install resources
    venv.pip_install buildpath

    pkgshare.install "skills", "optional-skills"

    %w[jarvis-prime jarvis jarvis-agent jarvis-acp hermes hermes-agent hermes-acp].each do |exe|
      next unless (libexec/"bin"/exe).exist?

      (bin/exe).write_env_script(
        libexec/"bin"/exe,
        HERMES_BUNDLED_SKILLS: pkgshare/"skills",
        HERMES_OPTIONAL_SKILLS: pkgshare/"optional-skills",
        HERMES_MANAGED: "homebrew"
      )
    end
  end

  test do
    assert_match "JARVIS Prime v#{version}", shell_output("#{bin}/jarvis-prime version")

    managed = shell_output("#{bin}/jarvis-prime update 2>&1")
    assert_match "managed by Homebrew", managed
    assert_match "brew upgrade jarvis-prime", managed
  end
end
