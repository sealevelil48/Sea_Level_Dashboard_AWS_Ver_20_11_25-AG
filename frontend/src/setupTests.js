import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';

// jsdom in CRA's Jest lacks these (react-router v7 needs them)
if (!global.TextEncoder) global.TextEncoder = TextEncoder;
if (!global.TextDecoder) global.TextDecoder = TextDecoder;
