import pytest

from validate_java_version_consistency import (
    extract_java_version_from_docker_tag,
    normalize_java_version,
    parse_docker_java_version,
    parse_docker_jdk_image,
    parse_gradle_java_version,
    resolve_args,
)


# ---------------------------------------------------------------------------
# normalize_java_version
# ---------------------------------------------------------------------------

class TestNormalizeJavaVersion:
    def test_plain_number(self):
        assert normalize_java_version("25") == "25"

    def test_strips_whitespace(self):
        assert normalize_java_version("  17  ") == "17"

    def test_strips_single_quotes(self):
        assert normalize_java_version("'21'") == "21"

    def test_strips_double_quotes(self):
        assert normalize_java_version('"11"') == "11"

    def test_legacy_1x_format_java_8(self):
        assert normalize_java_version("1.8") == "8"

    def test_legacy_1x_format_java_11(self):
        assert normalize_java_version("1.11") == "11"

    def test_gradle_java_version_constant(self):
        assert normalize_java_version("JavaVersion.VERSION_25") == "25"

    def test_gradle_java_version_constant_11(self):
        assert normalize_java_version("JavaVersion.VERSION_11") == "11"

    def test_leading_zeros_stripped(self):
        # int() conversion removes leading zeros
        assert normalize_java_version("011") == "11"

    # --- sad paths ---

    def test_none_input(self):
        assert normalize_java_version(None) is None

    def test_empty_string(self):
        assert normalize_java_version("") is None

    def test_only_whitespace(self):
        assert normalize_java_version("   ") is None

    def test_unexpanded_placeholder(self):
        assert normalize_java_version("${java.version}") is None

    def test_no_digits(self):
        assert normalize_java_version("abc") is None


# ---------------------------------------------------------------------------
# extract_java_version_from_docker_tag
# ---------------------------------------------------------------------------

class TestExtractJavaVersionFromDockerTag:
    def test_plain_number(self):
        assert extract_java_version_from_docker_tag("25") == "25"

    def test_hsl_base_image_jre_tag(self):
        assert extract_java_version_from_docker_tag("1.0.2-25-java-jre") == "25"

    def test_hsl_base_image_jdk_tag(self):
        assert extract_java_version_from_docker_tag("1.0.2-25-java-jdk") == "25"

    def test_version_dash_jdk(self):
        assert extract_java_version_from_docker_tag("25-jdk") == "25"

    def test_version_dash_jre(self):
        assert extract_java_version_from_docker_tag("25-jre") == "25"

    def test_java_dash_version(self):
        assert extract_java_version_from_docker_tag("java-11") == "11"

    def test_case_insensitive_jdk(self):
        assert extract_java_version_from_docker_tag("17-JDK") == "17"

    # --- sad paths ---

    def test_latest_tag(self):
        assert extract_java_version_from_docker_tag("latest") is None

    def test_empty_tag(self):
        assert extract_java_version_from_docker_tag("") is None

    def test_no_java_version_hint(self):
        assert extract_java_version_from_docker_tag("ubuntu") is None


# ---------------------------------------------------------------------------
# resolve_args
# ---------------------------------------------------------------------------

class TestResolveArgs:
    def test_curly_brace_syntax(self):
        assert resolve_args("${BASE}", {"BASE": "ubuntu:22.04"}) == "ubuntu:22.04"

    def test_dollar_word_syntax(self):
        assert resolve_args("$VERSION", {"VERSION": "1.0"}) == "1.0"

    def test_embedded_variable(self):
        assert resolve_args("prefix-${TAG}-suffix", {"TAG": "foo"}) == "prefix-foo-suffix"

    def test_multiple_variables(self):
        assert resolve_args("${A}/${B}", {"A": "x", "B": "y"}) == "x/y"

    def test_no_variables(self):
        assert resolve_args("plain-string", {}) == "plain-string"

    # --- sad paths ---

    def test_missing_curly_brace_variable_left_intact(self):
        assert resolve_args("${MISSING}", {}) == "${MISSING}"

    def test_missing_dollar_word_variable_left_intact(self):
        assert resolve_args("$MISSING", {}) == "$MISSING"

    def test_empty_string(self):
        assert resolve_args("", {}) == ""


# ---------------------------------------------------------------------------
# parse_docker_java_version  (uses tmp_path fixture)
# ---------------------------------------------------------------------------

class TestParseDockerJavaVersion:
    def test_simple_jre_tag(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jre\n"
        )
        version, image_ref = parse_docker_java_version(str(dockerfile))
        assert version == "25"
        assert "1.0.2-25-java-jre" in image_ref

    def test_multistage_uses_last_non_scratch(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk AS build\n"
            "FROM scratch\n"
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jre\n"
        )
        version, image_ref = parse_docker_java_version(str(dockerfile))
        assert version == "25"
        assert "java-jre" in image_ref

    def test_scratch_is_skipped_when_real_image_exists(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-17-java-jre AS base\n"
            "FROM scratch\n"
        )
        # scratch is not the last non-scratch image; base is
        version, _ = parse_docker_java_version(str(dockerfile))
        assert version == "17"

    def test_comments_are_ignored(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "# syntax=docker/dockerfile:1\n"
            "# This is a comment\n"
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-11-java-jre\n"
        )
        version, _ = parse_docker_java_version(str(dockerfile))
        assert version == "11"

    def test_image_with_digest_strips_digest(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jre@sha256:abc123\n"
        )
        version, _ = parse_docker_java_version(str(dockerfile))
        assert version == "25"

    # --- sad paths ---

    def test_no_from_instruction_raises(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("RUN echo hello\n")
        with pytest.raises(RuntimeError, match="Could not find a runtime image"):
            parse_docker_java_version(str(dockerfile))

    def test_only_scratch_raises(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM scratch\n")
        with pytest.raises(RuntimeError, match="Could not find a runtime image"):
            parse_docker_java_version(str(dockerfile))

    def test_image_without_tag_raises(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM ubuntu\n")
        with pytest.raises(RuntimeError, match="Could not determine the Java tag"):
            parse_docker_java_version(str(dockerfile))

    def test_unrecognizable_java_version_in_tag_raises(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM ubuntu:latest\n")
        with pytest.raises(RuntimeError, match="Could not determine the Java version"):
            parse_docker_java_version(str(dockerfile))


# ---------------------------------------------------------------------------
# parse_docker_jdk_image  (uses tmp_path fixture)
# ---------------------------------------------------------------------------

class TestParseDockerJdkImage:
    def test_standard_multistage_returns_first_real_from(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk AS base\n"
            "FROM base AS test\n"
            "FROM base AS build\n"
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jre\n"
        )
        image = parse_docker_jdk_image(str(dockerfile))
        assert image == "hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk"

    def test_single_stage_returns_only_image(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk\n"
        )
        image = parse_docker_jdk_image(str(dockerfile))
        assert image == "hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk"

    def test_skips_scratch(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM scratch\n"
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk AS base\n"
        )
        image = parse_docker_jdk_image(str(dockerfile))
        assert "java-jdk" in image

    def test_skips_stage_aliases(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk AS base\n"
            "FROM base AS test\n"
        )
        image = parse_docker_jdk_image(str(dockerfile))
        assert image == "hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk"

    def test_comments_are_ignored(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "# syntax=docker/dockerfile:1\n"
            "# check=error=true\n"
            "FROM hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk AS base\n"
        )
        image = parse_docker_jdk_image(str(dockerfile))
        assert "java-jdk" in image

    def test_no_real_from_raises(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM scratch\n")
        with pytest.raises(RuntimeError, match="Could not find a JDK base image"):
            parse_docker_jdk_image(str(dockerfile))

    def test_only_aliases_raises(self, tmp_path):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM base AS test\n"
            "FROM build AS final\n"
        )
        with pytest.raises(RuntimeError, match="Could not find a JDK base image"):
            parse_docker_jdk_image(str(dockerfile))


# ---------------------------------------------------------------------------
# parse_gradle_java_version  (uses tmp_path fixture)
# ---------------------------------------------------------------------------

class TestParseGradleJavaVersion:
    def test_jvm_target_string(self, tmp_path):
        gradle = tmp_path / "build.gradle.kts"
        gradle.write_text('compileKotlin { kotlinOptions { jvmTarget = "25" } }\n')
        version, source = parse_gradle_java_version(str(gradle))
        assert version == "25"
        assert "25" in source

    def test_jvm_target_java_version_constant(self, tmp_path):
        gradle = tmp_path / "build.gradle.kts"
        gradle.write_text("tasks.withType<KotlinCompile> { jvmTarget = JavaVersion.VERSION_17 }\n")
        version, _ = parse_gradle_java_version(str(gradle))
        assert version == "17"

    def test_language_version_set(self, tmp_path):
        gradle = tmp_path / "build.gradle.kts"
        gradle.write_text(
            "java { toolchain { languageVersion.set(JavaLanguageVersion.of(21)) } }\n"
        )
        version, _ = parse_gradle_java_version(str(gradle))
        assert version == "21"

    def test_source_compatibility(self, tmp_path):
        gradle = tmp_path / "build.gradle"
        gradle.write_text("sourceCompatibility = JavaVersion.VERSION_11\n")
        version, _ = parse_gradle_java_version(str(gradle))
        assert version == "11"

    def test_target_compatibility(self, tmp_path):
        gradle = tmp_path / "build.gradle"
        gradle.write_text("targetCompatibility = JavaVersion.VERSION_11\n")
        version, _ = parse_gradle_java_version(str(gradle))
        assert version == "11"

    def test_source_name_in_reported_source(self, tmp_path):
        gradle = tmp_path / "build.gradle.kts"
        gradle.write_text('compileKotlin { kotlinOptions { jvmTarget = "25" } }\n')
        _, source = parse_gradle_java_version(str(gradle))
        assert "build.gradle.kts" in source

    # --- sad paths ---

    def test_no_matching_pattern_raises(self, tmp_path):
        gradle = tmp_path / "build.gradle.kts"
        gradle.write_text("plugins { kotlin(\"jvm\") }\n")
        with pytest.raises(RuntimeError, match="Could not determine the Java version"):
            parse_gradle_java_version(str(gradle))

    def test_empty_file_raises(self, tmp_path):
        gradle = tmp_path / "build.gradle.kts"
        gradle.write_text("")
        with pytest.raises(RuntimeError, match="Could not determine the Java version"):
            parse_gradle_java_version(str(gradle))
