import React, { useId } from 'react';

/** Original vector objects: no external images, fonts, or tracking requests. */
export default function Signifier({ kind, className = '' }) {
  const id = useId().replace(/:/g, '');
  const paint = (name) => `url(#${id}-${name})`;
  return (
    <svg
      className={`future-signifier ${className}`}
      viewBox="0 0 200 160"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient
          id={`${id}-gold`}
          x1="50"
          y1="35"
          x2="145"
          y2="133"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#f6d48b" />
          <stop offset=".4" stopColor="#bfa36c" />
          <stop offset=".65" stopColor="#776342" />
          <stop offset="1" stopColor="#dfba71" />
        </linearGradient>
        <linearGradient
          id={`${id}-glass`}
          x1="40"
          y1="20"
          x2="145"
          y2="132"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#b8e3f8" stopOpacity=".8" />
          <stop offset=".5" stopColor="#65addf" stopOpacity=".32" />
          <stop offset="1" stopColor="#258bcc" stopOpacity=".65" />
        </linearGradient>
        <radialGradient id={`${id}-stone`} cx=".3" cy=".18" r=".9">
          <stop stopColor="#818385" />
          <stop offset=".45" stopColor="#515658" />
          <stop offset="1" stopColor="#242a2d" />
        </radialGradient>
        <linearGradient
          id={`${id}-silver`}
          x1="60"
          y1="25"
          x2="122"
          y2="138"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#e4e8e2" />
          <stop offset=".6" stopColor="#8c969c" />
          <stop offset="1" stopColor="#d7d8cc" />
        </linearGradient>
        <radialGradient id={`${id}-pearl`} cx=".3" cy=".2" r="1">
          <stop stopColor="#f4e8cd" />
          <stop offset=".6" stopColor="#c1b8a0" />
          <stop offset="1" stopColor="#685f51" />
        </radialGradient>
        <filter
          id={`${id}-shadow`}
          x="-70%"
          y="-70%"
          width="240%"
          height="240%"
        >
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>
      <ellipse
        cx="100"
        cy="138"
        rx="36"
        ry="5"
        fill="#000"
        opacity=".35"
        filter={paint('shadow')}
      />
      {kind === 'thread' && (
        <g strokeLinecap="round">
          <path
            d="M49 131C60 122 72 122 84 99C112 49 141 77 123 102C108 124 59 99 73 62C86 26 120 48 99 73C87 89 78 85 102 88C129 90 155 54 145 34"
            stroke="#601f25"
            strokeWidth="6"
          />
          <path
            d="M49 129C60 120 72 120 84 97C112 47 141 75 123 100C108 122 59 97 73 60C86 24 120 46 99 71C87 87 78 83 102 86C129 88 155 52 145 32"
            stroke="#d77570"
            strokeWidth="3.5"
          />
          <path
            d="M73 60C86 24 120 46 99 71M103 86C129 88 155 52 145 32"
            stroke="#f2a19a"
            strokeWidth="1"
          />
        </g>
      )}
      {kind === 'stone' && (
        <g transform="rotate(-13 100 90)">
          <path
            d="M47 102C39 78 64 47 98 46C130 43 152 67 153 91C156 117 132 129 98 128C74 128 53 119 47 102Z"
            fill={paint('stone')}
            stroke="#939994"
            strokeOpacity=".25"
          />
          <path
            d="M58 87C79 60 114 54 138 75"
            stroke="#afada0"
            strokeOpacity=".18"
          />
          <path
            d="M53 103C86 105 102 82 146 93"
            stroke="#adb0a3"
            strokeOpacity=".24"
          />
          <path
            d="M65 114C90 122 119 99 148 106"
            stroke="#d8cdb4"
            strokeOpacity=".18"
          />
        </g>
      )}
      {kind === 'cube' && (
        <g stroke="#a8d9f5" strokeOpacity=".65" strokeWidth="1">
          <path d="m100 25 49 28v58l-49 29-49-29V53Z" fill={paint('glass')} />
          <path d="m51 53 49 29 49-29M100 82v58" />
          <path
            d="m51 111 49-29 49 29M100 25v57"
            strokeDasharray="2 3"
            strokeOpacity=".23"
          />
          <path d="m54 55 46 27v53" stroke="#e3f4ff" strokeOpacity=".8" />
          <path d="m100 29 44 25-44 25-44-25Z" fill="#c5e4f4" opacity=".13" />
        </g>
      )}
      {kind === 'key' && (
        <g transform="rotate(38 100 80)" stroke={paint('gold')}>
          <circle cx="100" cy="52" r="22" strokeWidth="9" />
          <path
            d="M100 75v57h23m-23-18h16"
            strokeWidth="9"
            strokeLinejoin="round"
          />
          <path d="M95 77v53" stroke="#fae4b5" strokeWidth="1.3" opacity=".7" />
        </g>
      )}
      {kind === 'circle' && (
        <g transform="rotate(-24 100 80)">
          <path
            d="M130 45a47 47 0 1 0 16 24"
            stroke="#b9c8cf"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path
            d="M129 45a47 47 0 1 0 14 58"
            stroke="#e4e9e4"
            strokeWidth=".7"
          />
          <circle cx="146" cy="69" r="2" fill="#8dc7ff" />
        </g>
      )}
      {kind === 'zero' && (
        <text
          x="100"
          y="124"
          textAnchor="middle"
          fill="#decaa4"
          fontFamily="Georgia,serif"
          fontSize="128"
          fontStyle="italic"
        >
          0
        </text>
      )}
      {kind === 'fork' && (
        <g
          transform="rotate(15 100 80)"
          stroke={paint('silver')}
          strokeWidth="7"
          strokeLinecap="round"
        >
          <path d="M82 31v49a18 18 0 0 0 36 0V31M100 99v34" />
          <path
            d="M81 34v42M117 34v42"
            stroke="#fff"
            strokeOpacity=".5"
            strokeWidth="1"
          />
        </g>
      )}
      {kind === 'map' && (
        <g stroke="#beb9a5" strokeWidth="1">
          <path
            d="m39 47 40-13 40 14 40-13v85l-40 13-40-14-40 13Z"
            fill="#c9c3ad"
          />
          <path d="m79 34 40 14v85l-40-14Z" fill="#898f81" />
          <path
            d="M49 64c38 37 57-8 98 8M47 102c51-13 35 13 101-12"
            stroke="#656e60"
            strokeWidth="2"
          />
          <path d="m79 34 0 85m40-71v85" />
          <path
            d="m70 47 26 68 39-58"
            stroke="#f3e1b5"
            strokeWidth="2"
            strokeDasharray="4 4"
          />
        </g>
      )}
      {kind === 'dots' && (
        <>
          <circle cx="77" cy="69" r="19" fill="#e3ac65" />
          <circle cx="122" cy="97" r="19" fill="#8cb9d0" />
          <path d="m79 95 39-27" stroke="#829099" strokeDasharray="2 5" />
        </>
      )}
      {kind === 'seed' && (
        <g transform="rotate(28 100 80)">
          <path
            d="M100 24c-28 27-35 54-29 74 8 30 42 35 53 8 11-27-4-61-24-82Z"
            fill={paint('pearl')}
          />
          <path
            d="M100 29c-5 37-7 59 0 91"
            stroke="#736d58"
            strokeOpacity=".45"
          />
        </g>
      )}
      {kind === 'shell' && (
        <g stroke={paint('pearl')} strokeLinecap="round">
          <path
            d="M101 82c-4-11-17-7-17 3 0 19 30 21 35 0 7-31-36-46-55-16-22 35 23 72 55 50 39-28 21-91-25-94"
            strokeWidth="9"
          />
          <path
            d="M101 82c-4-11-17-7-17 3 0 19 30 21 35 0 7-31-36-46-55-16-22 35 23 72 55 50 39-28 21-91-25-94"
            stroke="#f2ddbf"
            strokeOpacity=".5"
            strokeWidth="1"
          />
        </g>
      )}
      {kind === 'orbit' && (
        <g transform="rotate(-30 100 80)">
          <ellipse
            cx="100"
            cy="80"
            rx="67"
            ry="29"
            stroke="#9fbaca"
            strokeWidth="1"
          />
          <circle cx="100" cy="80" r="16" fill={paint('pearl')} />
          <circle cx="160" cy="93" r="5" fill="#8dc7ff" />
          <ellipse
            cx="100"
            cy="80"
            rx="36"
            ry="60"
            stroke="#9fbaca"
            strokeOpacity=".3"
          />
        </g>
      )}
    </svg>
  );
}
