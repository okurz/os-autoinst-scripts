# Copyright SUSE LLC
"""Common error handling for Python-based scripts."""


def decode_output(output: bytes | None) -> str:
    """Returns the string representation for the specified output (typically stderr)."""
    return output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)


def is_404_str(output_str: str) -> bool:
    """Returns whether the specified output string represents a 404 error."""
    return "404" in output_str and "Not Found" in output_str


def is_404(output: bytes | None) -> bool:
    """Returns whether the specified output (raw stderr) represents a 404 error."""
    return is_404_str(decode_output(output))
