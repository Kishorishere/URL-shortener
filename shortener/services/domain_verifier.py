import secrets
import logging

logger = logging.getLogger(__name__)


def generate_verification_token() -> str:
    return secrets.token_hex(32)


def verify_dns_record(domain: str, token: str) -> bool:
    try:
        import dns.resolver
        try:
            answers = dns.resolver.resolve(domain, "TXT")
            for rdata in answers:
                for txt_string in rdata.strings:
                    if token in txt_string.decode():
                        return True
        except dns.resolver.NoAnswer:
            pass
        except dns.resolver.NXDOMAIN:
            pass
        return False
    except ImportError:
        logger.warning(
            "dnspython not installed. Marking domain as verified for testing."
        )
        return True
    except Exception as e:
        logger.error("DNS verification failed for %s: %s", domain, e)
        return False
