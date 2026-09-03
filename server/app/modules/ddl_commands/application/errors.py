"""Application-level exception types, one per concept until this file is
large enough to split."""


class BuyerNotFoundError(Exception):
    pass


class BuyerAlreadyExistsError(Exception):
    pass


class SellerNotFoundError(Exception):
    pass


class SellerAlreadyExistsError(Exception):
    pass
