import shutil, errno, hashlib, os
from pathlib import Path

from gradio_client.utils import strip_invalid_filename_characters


def hash_file(file_path, chunk_num_blocks: int = 128) -> str:
    """Plain sha256 of file content (no gradio random seed, so dedup survives restarts)."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_num_blocks * sha.block_size), b""):
            sha.update(chunk)
    return sha.hexdigest()


# end def


def save_file_to_cache(source_path, cache_dir) -> str:
    """Same layout/dedup as gradio's processing_utils.save_file_to_cache
    (cache_dir/<sha256>/<basename>), but with an exFAT-safe EPERM retry."""
    temp_dir = Path(cache_dir) / hash_file(source_path)
    temp_dir.mkdir(exist_ok=True, parents=True)
    name = strip_invalid_filename_characters(Path(source_path).name)
    final_path = str(temp_dir / name)
    if not os.path.exists(final_path):
        try:
            shutil.copy2(source_path, final_path)
        except PermissionError as _pe:
            if _pe.errno == errno.EPERM:
                shutil.copyfile(source_path, final_path)  # exFAT: copy without metadata
            else:
                raise
            # end if
        # end try
    # end if
    return final_path


# end def


def copyfile(
    source_path: str, final_path: str, filename: str, log_prefix="[load]"
) -> bool:
    try:
        shutil.copy2(source_path, final_path)
        print(
            f"{log_prefix} Successfully copied '{source_path}' to '{final_path}' and preserved metadata."
        )
    except FileNotFoundError:
        print(f"{log_prefix} Error: Source file '{source_path}' not found.")
        return False
    except PermissionError as _pe:
        print(
            f"{log_prefix} Failed to copy due to permissions: {_pe}. Try running with elevated privileges."
        )
        if _pe.errno == errno.EPERM:
            try:
                shutil.copyfile(source_path, final_path)
                print(
                    f"{log_prefix} Successfully copied '{source_path}' to '{final_path}' without metadata."
                )
                return True
            except Exception as _cpe:
                print(f"{log_prefix} Error copying {filename} without metadata: {_cpe}")
                return False
            # end try
        # end if
        return False
    except Exception as e:
        print(f"{log_prefix} Error copying {filename}: {e}")
        return False
    # end try


# end def
