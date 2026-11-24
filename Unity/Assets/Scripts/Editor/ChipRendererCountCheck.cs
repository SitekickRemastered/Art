using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Compares the renderers a chip prefab declares in its YAML with the ones Unity
/// actually loads.  A block header with no body -- chip 74's
/// `--- !u!114 &100020` lines -- truncates the load, so the prefab still reads
/// as complete while the spawned effect has fewer renderers than it was drawn
/// with.  ChipPlayCheck only sees that when a piece is missing badly enough to
/// fail, so this compares every chip.
/// Batch: -executeMethod ChipRendererCountCheck.RunFromCommandLine
/// </summary>
public static class ChipRendererCountCheck
{
	const string CHIPS = "Assets/Chips";
	const string REPORT = "Logs/chip-renderer-counts.txt";

	static readonly Regex Header = new Regex( @"^--- !u!(\d+) &(-?\d+)[^\n]*$", RegexOptions.Multiline );

	public static void RunFromCommandLine()
	{
		var paths = AssetDatabase.FindAssets( "t:Prefab", new[] { CHIPS } )
			.Select( AssetDatabase.GUIDToAssetPath )
			.Where( p => Regex.IsMatch( p, @"Chip_\d{4}_Effect\.prefab$" ) )
			.OrderBy( p => p )
			.ToArray();

		var report = new StringBuilder();
		var problems = new List<string>();
		int declaredTotal = 0, loadedTotal = 0, emptyHeaders = 0;

		foreach ( var path in paths )
		{
			var text = File.ReadAllText( path );
			var matches = Header.Matches( text );
			int declared = 0;
			var empty = new List<string>();
			for ( var i = 0; i < matches.Count; i++ )
			{
				var start = matches[ i ].Index + matches[ i ].Length;
				var end = i + 1 < matches.Count ? matches[ i + 1 ].Index : text.Length;
				if ( text.Substring( start, end - start ).Trim().Length == 0 )
				{
					empty.Add( "!u!" + matches[ i ].Groups[ 1 ].Value + " &" + matches[ i ].Groups[ 2 ].Value );
					continue;
				}

				if ( matches[ i ].Groups[ 1 ].Value == "212" )
					declared++;
			}

			var prefab = AssetDatabase.LoadAssetAtPath<GameObject>( path );
			var renderers = prefab != null
				? prefab.GetComponentsInChildren<SpriteRenderer>( true )
				: new SpriteRenderer[ 0 ];
			var loaded = renderers.Length;
			var withSprite = renderers.Count( r => r.sprite != null );

			declaredTotal += declared;
			loadedTotal += loaded;
			emptyHeaders += empty.Count;

			if ( prefab == null || loaded != declared || empty.Count > 0 )
				problems.Add( path + ": declared " + declared + " loaded " + loaded
					+ " sprites " + withSprite
					+ ( empty.Count > 0 ? "  empty blocks: " + string.Join( ",", empty.ToArray() ) : "" ) );
		}

		report.AppendLine( "Chip effect prefabs: " + paths.Length );
		report.AppendLine( "SpriteRenderers declared: " + declaredTotal + "  loaded: " + loadedTotal );
		report.AppendLine( "Empty block headers: " + emptyHeaders );
		report.AppendLine( "Prefabs that silently under-load: " + problems.Count );
		foreach ( var p in problems )
			report.AppendLine( "  " + p );
		report.AppendLine();
		report.AppendLine( problems.Count == 0
			? "RESULT: OK - every chip loads every renderer its prefab declares."
			: "RESULT: FAIL - " + problems.Count + " prefabs load fewer renderers than they declare." );

		Directory.CreateDirectory( Path.GetDirectoryName( REPORT ) );
		File.WriteAllText( REPORT, report.ToString() );
		Debug.Log( report.ToString() );
		EditorApplication.Exit( problems.Count == 0 ? 0 : 1 );
	}
}
