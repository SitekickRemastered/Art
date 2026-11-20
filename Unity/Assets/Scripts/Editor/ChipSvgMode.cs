#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.U2D;
using Unity.VectorGraphics.Editor;

namespace Sitekick
{
	/// <summary>
	/// Reports what the chip SVG importers produce. The chips are vector
	/// sprites, so the report should show no raster textures: the build carries
	/// tessellated geometry instead of a texture per chip.
	/// </summary>
	public static class ChipSvgMode
	{
		public const string ReportPath = "Logs/chip-svg-mode.txt";
		public const string Root = "Assets/Chips";

		[MenuItem( "Sitekick/Chip SVG/Report" )]
		public static void ReportFromMenu()
		{
			Report();
		}

		/// <summary>Batch entry point: <c>-executeMethod Sitekick.ChipSvgMode.Check</c>.</summary>
		public static void Check()
		{
			Report();
		}

		public static string[] Paths()
		{
			return Directory.GetFiles( Root, "*.svg", SearchOption.AllDirectories )
				.Select( p => p.Replace( '\\', '/' ) )
				.OrderBy( p => p, StringComparer.Ordinal )
				.ToArray();
		}

		public static void Report()
		{
			var lines = new List<string>();
			var paths = Paths();

			long texture = 0, vertices = 0;
			int sprites = 0, largest = 0, raster = 0, empty = 0;
			string largestPath = "";

			foreach ( var path in paths )
			{
				var sprite = AssetDatabase.LoadAssetAtPath<Sprite>( path );
				if ( sprite == null )
				{
					lines.Add( "no sprite: " + path );
					continue;
				}

				sprites++;
				var tex = sprite.texture;
				int side = tex != null ? Mathf.Max( tex.width, tex.height ) : 0;
				texture += tex != null ? tex.width * (long)tex.height * 4L : 0L;
				vertices += sprite.vertices.Length;

				if ( side > largest )
				{
					largest = side;
					largestPath = path;
				}

				if ( side > 512 )
					raster++;

				if ( sprite.vertices.Length == 0 && IsVector( path ) )
					empty++;
			}

			lines.Add( "sprites: " + sprites );
			lines.Add( "texture payload: " + ( texture / 1048576.0 ).ToString( "0.0" ) + " MiB" );
			lines.Add( "largest texture: " + largest + " px (" + largestPath + ")" );
			lines.Add( "sprites with a texture over 512 px: " + raster );
			lines.Add( "sprite vertices total: " + vertices );
			lines.Add( "vector sprites with no geometry: " + empty );
			lines.Add( "RESULT: " + ( sprites > 0 ? "OK" : "FAIL" ) );
			Write( lines );
		}

		static bool IsVector( string path )
		{
			var importer = AssetImporter.GetAtPath( path ) as SVGImporter;
			return importer != null && importer.SvgType == SVGType.VectorSprite;
		}

		static void Write( List<string> lines )
		{
			Directory.CreateDirectory( Path.GetDirectoryName( ReportPath ) );
			File.WriteAllLines( ReportPath, lines );
			Debug.Log( string.Join( "\n", lines.ToArray() ) );
		}
	}
}
#endif
