class RTMP_ChunkNotFullyReceived(BaseException):
    pass


class RTMP_NotHeader(BaseException):
    pass


class RTMP_MultiplePacketsInBuffer(BaseException):
    pass
