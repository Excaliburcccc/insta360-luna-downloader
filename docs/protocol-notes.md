# Luna Local Protocol Notes

These notes document the minimum behavior needed by this downloader.

## Network

- Camera host: `192.168.42.1`
- HTTP file service: TCP `80`
- Control service: TCP `6666`

## Authorization Session

Direct HTTP requests to `/storage_internal/DCIM/Camera01/` return `401
Unauthorized` from the PC until a short control session is opened on port
`6666`.

The downloader sends two binary messages that begin with the `UCD2` magic and
keeps the TCP control connection open while listing or downloading files:

```text
55 43 44 32 01 0c 05 0f 00 00 00 00 37 05 47 7c
55 43 44 32 01 0c 04 10 0f 00 00 00 08 00 02 01
00 00 80 00 00 08 30 08 0f 08 0b 7c 00 8e 7c
```

After this handshake, HTTP directory and file requests return `200 OK` or `206
Partial Content`.

## File Listing

The camera serves an nginx directory index at:

```text
http://192.168.42.1/storage_internal/DCIM/Camera01/
```

Example entries:

```html
<a href="VID_20260614_121357_007.mp4">VID_20260614_121357_007.mp4</a> 14-Jun-2026 12:13 11M
```

## Download

Files are downloaded with HTTP `Range` requests. Existing partial files can be
resumed by sending:

```text
Range: bytes=<existing-size>-
```

