#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <ctype.h>
#include <stdbool.h>
#include "Attocube.Common.NativeC.h"


/*H**********************************************************************
*
* DESCRIPTION :
*       This is an exemplary implementation of the C API for the IDS streaming feature.
*       The program streams and decodes 1023 position values with a streaming rate of 100 kHz from axis 1 and 3.
*
* CREATED : 29.10.2018
*           Copyright attocube systems AG, 2018.  All rights reserved.
*
*H*/


int main()
{
    void* stream = OpenStream("192.168.1.1", true, 10, 1 | 4 ); // stream data with 100 kHz from axis 1 and 3

    unsigned char buffer[8192 << 1]; /* 8192 * 2 */
    int count = ReadStream(stream, buffer, sizeof(buffer));

    /** @todo Get rid of the typecast */
    printf("Size of buffer is: %lu\nCount is: %i\n", (long unsigned int)sizeof(buffer), count);

    int64_t x[1024],
            y[1024],
            z[1024];
    int64_t* axes[] = { x, y, z };
    int destBufferSize = sizeof(x) * 3;

    int decodedSamplesCount;
    int decodedBytes = DecodeStream(stream, buffer, count, axes, destBufferSize, &decodedSamplesCount);

    CloseStream(stream);

    for( int i = 0; i < 1023; ++i )
    {

        printf("%I64d\t %I64d\t %I64d\n", x[i], y[i], z[i]);

    }
    printf("Decoded samples count: %i\nDecoded bytes: %i\n", decodedSamplesCount, decodedBytes);

    printf("Done!\n");
    return EXIT_SUCCESS;
}

