import shutil, errno


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
