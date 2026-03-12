import os
import re
import subprocess
import sys


def normalize_java_version(value):
    if not value:
        return None

    cleaned = value.strip().strip('"\'')
    if not cleaned or cleaned.startswith('${'):
        return None

    cleaned = cleaned.replace('JavaVersion.VERSION_', '')

    if cleaned.startswith('1.'):
        parts = cleaned.split('.')
        if len(parts) > 1 and parts[1].isdigit():
            return parts[1]

    match = re.search(r'(\d+)', cleaned)
    if match:
        return str(int(match.group(1)))

    return None


def extract_java_version_from_docker_tag(tag):
    patterns = (
        r'(?:^|[._-])(\d+)(?:[._-])java(?:[._-])(jre|jdk)(?:$|[._-])',
        r'(?:^|[._-])java(?:[._-])(\d+)(?:$|[._-])',
        r'(?:^|[._-])(\d+)(?:[._-])(jre|jdk)(?:$|[._-])',
        r'^(\d+)$',
    )

    for pattern in patterns:
        match = re.search(pattern, tag, re.IGNORECASE)
        if match:
            return normalize_java_version(match.group(1))

    return None


def resolve_args(value, args):
    def replace(match):
        variable_name = match.group(1) or match.group(2)
        return args.get(variable_name, match.group(0))

    return re.sub(r'\$\{([^}]+)\}|\$(\w+)', replace, value)


def _is_stage_alias(image):
    """Return True if the image string is a multi-stage alias (e.g. 'base', 'build'), not a registry reference."""
    return ':' not in image and '/' not in image


def parse_docker_jdk_image(dockerfile_path):
    """Return the image ref of the first real (non-scratch, non-alias) FROM stage.

    In the standard 4-stage Java Dockerfile pattern the first real FROM is the JDK
    build/test image, e.g. hsldevcom/infodevops-docker-base-images:1.0.2-25-java-jdk.
    """
    args = {}

    with open(dockerfile_path, encoding='utf-8') as dockerfile:
        for raw_line in dockerfile:
            line = raw_line.split('#', 1)[0].strip()
            if not line:
                continue

            from_match = re.match(r'^FROM\s+([^\s]+)', line, re.IGNORECASE)
            if from_match:
                image = resolve_args(from_match.group(1).strip(), args)
                if image.lower() != 'scratch' and not _is_stage_alias(image):
                    return image

    raise RuntimeError('Could not find a JDK base image in Dockerfile.')


def parse_docker_java_version(dockerfile_path):
    args = {}
    images = []

    with open(dockerfile_path, encoding='utf-8') as dockerfile:
        for raw_line in dockerfile:
            line = raw_line.split('#', 1)[0].strip()
            if not line:
                continue

            arg_match = re.match(r'^ARG\s+([A-Za-z_][A-Za-z0-9_]*)=(.+)$', line, re.IGNORECASE)
            if arg_match:
                args[arg_match.group(1)] = arg_match.group(2).strip()
                continue

            from_match = re.match(r'^FROM\s+([^\s]+)', line, re.IGNORECASE)
            if from_match:
                image = resolve_args(from_match.group(1).strip(), args)
                images.append(image)

    runtime_images = [image for image in images if image.lower() != 'scratch']
    if not runtime_images:
        raise RuntimeError('Could not find a runtime image in Dockerfile.')

    image_ref = runtime_images[-1].split('@', 1)[0]
    last_slash = image_ref.rfind('/')
    last_colon = image_ref.rfind(':')

    if last_colon <= last_slash:
        raise RuntimeError(f'Could not determine the Java tag from Docker image "{image_ref}".')

    tag = image_ref[last_colon + 1 :]
    java_version = extract_java_version_from_docker_tag(tag)
    if not java_version:
        raise RuntimeError(
            'Could not determine the Java version from Docker tag '
            f'"{tag}". Expected a tag like "25", "25-jdk", or "1.0.2-25-java-jre".'
        )

    return java_version, image_ref


def evaluate_maven_property(expression):
    result = subprocess.run(
        [
            'mvn',
            '-q',
            '-DforceStdout',
            '-Dstyle.color=never',
            'help:evaluate',
            f'-Dexpression={expression}',
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return None

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    lines = [line for line in lines if not line.startswith('[')]
    return lines[-1] if lines else None


def parse_maven_java_version():
    for expression in (
        'maven.compiler.release',
        'maven.compiler.target',
        'java.version',
    ):
        value = evaluate_maven_property(expression)
        normalized = normalize_java_version(value)
        if normalized:
            return normalized, f'pom.xml ({expression}={value})'

    raise RuntimeError(
        'Could not determine the Java version from pom.xml. '
        'Expected maven.compiler.release, maven.compiler.target, or java.version.'
    )


def parse_gradle_java_version(gradle_path):
    with open(gradle_path, encoding='utf-8') as gradle_file:
        content = gradle_file.read()

    patterns = [
        r'jvmTarget\s*=\s*["\']([^"\']+)["\']',
        r'jvmTarget\s*=\s*JavaVersion\.VERSION_?(\d+)',
        r'languageVersion(?:\.set)?\s*\(?\s*JavaLanguageVersion\.of\((\d+)\)\s*\)?',
        r'sourceCompatibility\s*=\s*JavaVersion\.VERSION_?(\d+)',
        r'targetCompatibility\s*=\s*JavaVersion\.VERSION_?(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            value = match.group(1)
            normalized = normalize_java_version(value)
            if normalized:
                return normalized, f'{os.path.basename(gradle_path)} ({value})'

    raise RuntimeError(
        'Could not determine the Java version from the Gradle build file. '
        'Expected compileKotlin.kotlinOptions.jvmTarget or java.toolchain.languageVersion.'
    )


def _write_github_file(env_var_name, content):
    """Append key=value to a GitHub Actions environment file if the path is set."""
    path = os.getenv(env_var_name)
    if path:
        with open(path, 'a') as f:
            f.write(f'{content}\n')


def main():
    dockerfile_path = os.path.join(os.getcwd(), 'Dockerfile')
    if not os.path.exists(dockerfile_path):
        raise RuntimeError(f'Dockerfile not found at {dockerfile_path}.')

    jdk_image = parse_docker_jdk_image(dockerfile_path)
    print(f'JDK base image: {jdk_image}')
    _write_github_file('GITHUB_OUTPUT', f'TEST_BASE_IMAGE={jdk_image}')
    _write_github_file('GITHUB_ENV', f'TEST_BASE_IMAGE={jdk_image}')

    docker_version, docker_image = parse_docker_java_version(dockerfile_path)

    pom_path = os.path.join(os.getcwd(), 'pom.xml')
    gradle_paths = [
        os.path.join(os.getcwd(), 'build.gradle.kts'),
        os.path.join(os.getcwd(), 'build.gradle'),
    ]

    if os.path.exists(pom_path):
        build_version, build_source = parse_maven_java_version()
    else:
        existing_gradle_paths = [path for path in gradle_paths if os.path.exists(path)]
        if not existing_gradle_paths:
            raise RuntimeError(
                'Could not find pom.xml, build.gradle.kts, or build.gradle in the working directory.'
            )
        build_version, build_source = parse_gradle_java_version(existing_gradle_paths[0])

    if docker_version != build_version:
        print(
            'Java version mismatch: '
            f'Dockerfile uses Java {docker_version} ({docker_image}), '
            f'but {build_source} resolves to Java {build_version}.',
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        'Java version check passed: '
        f'Dockerfile uses Java {docker_version} and {build_source} matches.'
    )


if __name__ == '__main__':
    main()
